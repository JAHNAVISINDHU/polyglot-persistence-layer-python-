const fs = require('fs');
const path = require('path');
const logger = require('../utils/logger');

const RETRY_QUEUE_PATH = process.env.RETRY_QUEUE_PATH || path.join('/app', 'retry_queue.json');

function readQueue() {
  try {
    if (!fs.existsSync(RETRY_QUEUE_PATH)) {
      fs.writeFileSync(RETRY_QUEUE_PATH, '[]', 'utf-8');
      return [];
    }
    const content = fs.readFileSync(RETRY_QUEUE_PATH, 'utf-8').trim();
    if (!content) return [];
    return JSON.parse(content);
  } catch (err) {
    logger.error('Failed to read retry queue', { error: err.message });
    return [];
  }
}

function writeQueue(queue) {
  try {
    fs.writeFileSync(RETRY_QUEUE_PATH, JSON.stringify(queue, null, 2), 'utf-8');
  } catch (err) {
    logger.error('Failed to write retry queue', { error: err.message });
  }
}

function enqueue(event) {
  const queue = readQueue();
  // Avoid duplicate entries in queue
  const exists = queue.some((e) => e.invoice_id === event.invoice_id);
  if (!exists) {
    queue.push(event);
    writeQueue(queue);
    logger.info('Event added to retry queue', { invoice_id: event.invoice_id, package_id: event.package_id });
  } else {
    logger.warn('Event already in retry queue, skipping', { invoice_id: event.invoice_id });
  }
}

function dequeue(invoiceId) {
  const queue = readQueue();
  const newQueue = queue.filter((e) => e.invoice_id !== invoiceId);
  writeQueue(newQueue);
}

function getAll() {
  return readQueue();
}

module.exports = { enqueue, dequeue, getAll, readQueue, writeQueue };
