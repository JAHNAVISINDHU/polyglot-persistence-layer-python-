const logger = require('../utils/logger');
const retryQueue = require('../utils/retryQueue');
const { checkPackageDelivered, insertInvoice } = require('../ingestion/eventHandlers');

async function runReconciliation() {
  const queue = retryQueue.getAll();

  if (queue.length === 0) {
    logger.info('Retry queue is empty, nothing to reconcile');
    return { processed: 0, remaining: 0 };
  }

  logger.info(`Starting reconciliation for ${queue.length} deferred events`);

  let processedCount = 0;

  for (const event of queue) {
    const { invoice_id, package_id, amount, customer_id, currency, timestamp, event_id } = event;

    const isDelivered = await checkPackageDelivered(package_id);

    if (!isDelivered) {
      logger.info('Package still not DELIVERED, keeping in retry queue', {
        package_id,
        invoice_id,
      });
      continue;
    }

    logger.info('Package is now DELIVERED, processing deferred billing event', {
      package_id,
      invoice_id,
    });

    try {
      await insertInvoice({ invoice_id, package_id, amount, customer_id, currency, timestamp, event_id });
      retryQueue.dequeue(invoice_id);
      processedCount++;
    } catch (err) {
      logger.error('Failed to process deferred billing event during reconciliation', {
        invoice_id,
        package_id,
        error: err.message,
      });
    }
  }

  const remaining = retryQueue.getAll().length;
  logger.info('Reconciliation complete', { processed: processedCount, remaining });
  return { processed: processedCount, remaining };
}

module.exports = { runReconciliation };
