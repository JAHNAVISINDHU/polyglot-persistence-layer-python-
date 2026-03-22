const postgres = require('../databases/postgres');
const mongo = require('../databases/mongo');
const neo4j = require('../databases/neo4j');
const retryQueue = require('../utils/retryQueue');
const logger = require('../utils/logger');

// ─── DRIVER_LOCATION_UPDATE ───────────────────────────────────────────────────

async function handleDriverLocationUpdate(event) {
  const { driver_id, latitude, longitude, zone_id, timestamp, event_id } = event;

  if (!driver_id || !zone_id) {
    logger.error('DRIVER_LOCATION_UPDATE missing required fields', { event_id });
    return;
  }

  const cypher = `
    MERGE (d:Driver {driverId: $driverId})
    SET d.latitude = $latitude,
        d.longitude = $longitude,
        d.lastSeen = $timestamp,
        d.eventId = $eventId
    MERGE (z:Zone {zoneId: $zoneId})
    MERGE (d)-[r:LOCATED_IN]->(z)
    SET r.timestamp = $timestamp
    RETURN d, z
  `;

  try {
    await neo4j.runQuery(cypher, {
      driverId: driver_id,
      latitude,
      longitude,
      timestamp,
      eventId: event_id,
      zoneId: zone_id,
    });
    logger.info('Driver location updated in Neo4j', { driver_id, zone_id });
  } catch (err) {
    logger.error('Failed to update driver location in Neo4j', {
      driver_id,
      error: err.message,
    });
    throw err;
  }
}

// ─── PACKAGE_STATUS_CHANGE ────────────────────────────────────────────────────

async function handlePackageStatusChange(event) {
  const { package_id, status, timestamp, driver_id, location, event_id } = event;

  if (!package_id || !status) {
    logger.error('PACKAGE_STATUS_CHANGE missing required fields', { event_id });
    return;
  }

  const statusEntry = {
    status,
    timestamp,
    driver_id,
    location,
    event_id,
  };

  try {
    const collection = await mongo.getCollection('packages');

    await collection.updateOne(
      { package_id },
      {
        $set: { package_id, updated_at: timestamp },
        $push: {
          status_history: {
            $each: [statusEntry],
            $sort: { timestamp: 1 },
          },
        },
      },
      { upsert: true }
    );

    logger.info('Package status updated in MongoDB', { package_id, status });
  } catch (err) {
    logger.error('Failed to update package status in MongoDB', {
      package_id,
      error: err.message,
    });
    throw err;
  }
}

// ─── BILLING_EVENT ────────────────────────────────────────────────────────────

async function handleBillingEvent(event) {
  const { invoice_id, package_id, amount, customer_id, currency, timestamp, event_id } = event;

  if (!invoice_id || !package_id) {
    logger.error('BILLING_EVENT missing required fields', { event_id });
    return;
  }

  // Check if package is delivered in MongoDB
  const isDelivered = await checkPackageDelivered(package_id);

  if (!isDelivered) {
    logger.warn('Package not yet DELIVERED, deferring billing event to retry queue', {
      package_id,
      invoice_id,
    });
    retryQueue.enqueue(event);
    return;
  }

  await insertInvoice({ invoice_id, package_id, amount, customer_id, currency, timestamp, event_id });
}

async function checkPackageDelivered(packageId) {
  try {
    const collection = await mongo.getCollection('packages');
    const doc = await collection.findOne({ package_id: packageId });

    if (!doc || !doc.status_history || doc.status_history.length === 0) {
      return false;
    }

    // Check the latest status
    const sorted = [...doc.status_history].sort(
      (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
    );
    return sorted[0].status === 'DELIVERED';
  } catch (err) {
    logger.error('Failed to check package delivery status', { packageId, error: err.message });
    return false;
  }
}

async function insertInvoice({ invoice_id, package_id, amount, customer_id, currency, timestamp, event_id }) {
  try {
    await postgres.query(
      `INSERT INTO invoices (invoice_id, package_id, amount, customer_id, currency, timestamp, event_id)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [invoice_id, package_id, amount, customer_id, currency || 'USD', timestamp, event_id]
    );
    logger.info('Invoice inserted into PostgreSQL', { invoice_id, package_id });
  } catch (err) {
    if (err.code === '23505') {
      // Unique violation
      logger.error('Duplicate invoice_id detected, skipping insertion', {
        invoice_id,
        package_id,
        error: err.message,
      });
    } else {
      logger.error('Failed to insert invoice into PostgreSQL', {
        invoice_id,
        error: err.message,
      });
      throw err;
    }
  }
}

module.exports = {
  handleDriverLocationUpdate,
  handlePackageStatusChange,
  handleBillingEvent,
  checkPackageDelivered,
  insertInvoice,
};
