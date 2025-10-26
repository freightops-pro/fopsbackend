/**
 * K6 Load Testing Script for FreightOps Pro
 * Tests system capacity for 5000+ concurrent users
 * 
 * Run with: k6 run k6-load-test.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
export let errorRate = new Rate('errors');
export let responseTime = new Trend('response_time');
export let requestCount = new Counter('requests');

// Test configuration
export let options = {
  stages: [
    // Warm-up phase
    { duration: '2m', target: 100 },   // Ramp up to 100 users
    { duration: '3m', target: 100 },   // Stay at 100 users
    
    // Scale-up phase
    { duration: '5m', target: 500 },   // Ramp up to 500 users
    { duration: '5m', target: 500 },   // Stay at 500 users
    
    // High-load phase
    { duration: '5m', target: 1000 },  // Ramp up to 1000 users
    { duration: '5m', target: 1000 },  // Stay at 1000 users
    
    // Peak load phase
    { duration: '5m', target: 2000 },  // Ramp up to 2000 users
    { duration: '5m', target: 2000 },  // Stay at 2000 users
    
    // Stress test phase
    { duration: '5m', target: 3000 },  // Ramp up to 3000 users
    { duration: '5m', target: 3000 },  // Stay at 3000 users
    
    // Extreme load phase
    { duration: '5m', target: 5000 },  // Ramp up to 5000 users
    { duration: '10m', target: 5000 }, // Stay at 5000 users
    
    // Cool-down phase
    { duration: '5m', target: 1000 },  // Ramp down to 1000 users
    { duration: '3m', target: 100 },   // Ramp down to 100 users
    { duration: '2m', target: 0 },     // Ramp down to 0 users
  ],
  
  thresholds: {
    // Performance thresholds
    'http_req_duration': ['p(95)<500', 'p(99)<1000'], // 95% under 500ms, 99% under 1000ms
    'http_req_failed': ['rate<0.01'],                  // Error rate under 1%
    'errors': ['rate<0.01'],                           // Custom error rate under 1%
    'response_time': ['p(95)<500'],                    // Custom response time metric
    
    // Load thresholds
    'http_reqs': ['rate>100'],                         // At least 100 requests/second
    'http_reqs': ['count>100000'],                     // At least 100k total requests
  },
  
  // Resource limits
  vus: 5000,  // Maximum virtual users
};

// Test data
const BASE_URL = __ENV.BASE_URL || 'https://api-production.railway.app';
const TEST_COMPANY_ID = __ENV.TEST_COMPANY_ID || 'TEST_COMPANY';
const TEST_EMAIL = __ENV.TEST_EMAIL || 'loadtest@freightops.com';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || 'LoadTest123!';

// Global variables
let authToken = null;
let companyId = null;

export function setup() {
  // Setup phase - authenticate and get test data
  console.log('Setting up load test...');
  
  const loginResponse = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({
    email: TEST_EMAIL,
    password: TEST_PASSWORD,
    companyId: TEST_COMPANY_ID
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
  
  if (loginResponse.status === 200) {
    const data = JSON.parse(loginResponse.body);
    authToken = data.access_token;
    companyId = data.company_id;
    console.log('Authentication successful');
    return { token: authToken, companyId: companyId };
  } else {
    console.error('Authentication failed:', loginResponse.body);
    return null;
  }
}

export default function(data) {
  if (!data || !data.token) {
    console.error('Setup failed, skipping test');
    return;
  }
  
  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'Content-Type': 'application/json'
  };
  
  // Test different user behaviors
  const userType = Math.random();
  
  if (userType < 0.3) {
    // 30% of users: Dashboard users (frequent page loads)
    testDashboardUser(headers, data.companyId);
  } else if (userType < 0.6) {
    // 30% of users: Fleet managers (fleet operations)
    testFleetManager(headers, data.companyId);
  } else if (userType < 0.8) {
    // 20% of users: Dispatchers (load management)
    testDispatcher(headers, data.companyId);
  } else {
    // 20% of users: Drivers (mobile app usage)
    testDriver(headers, data.companyId);
  }
  
  // Add some randomness to user behavior
  sleep(Math.random() * 2 + 0.5); // 0.5-2.5 seconds between actions
}

function testDashboardUser(headers, companyId) {
  group('Dashboard User', function() {
    // Load dashboard data
    let response = http.get(`${BASE_URL}/api/performance/dashboard`, { headers });
    check(response, {
      'dashboard load successful': (r) => r.status === 200,
      'dashboard response time < 500ms': (r) => r.timings.duration < 500,
    });
    errorRate.add(response.status >= 400);
    responseTime.add(response.timings.duration);
    requestCount.add(1);
    
    // Load performance metrics
    response = http.get(`${BASE_URL}/api/performance/metrics/summary`, { headers });
    check(response, {
      'metrics load successful': (r) => r.status === 200,
    });
    errorRate.add(response.status >= 400);
    responseTime.add(response.timings.duration);
    requestCount.add(1);
  });
}

function testFleetManager(headers, companyId) {
  group('Fleet Manager', function() {
    // Load fleet data
    let response = http.get(`${BASE_URL}/api/performance/fleet`, { headers });
    check(response, {
      'fleet data load successful': (r) => r.status === 200,
      'fleet response time < 500ms': (r) => r.timings.duration < 500,
    });
    errorRate.add(response.status >= 400);
    responseTime.add(response.timings.duration);
    requestCount.add(1);
    
    // Load vehicles
    response = http.get(`${BASE_URL}/api/fleet/vehicles`, { headers });
    check(response, {
      'vehicles load successful': (r) => r.status === 200,
    });
    errorRate.add(response.status >= 400);
    responseTime.add(response.timings.duration);
    requestCount.add(1);
    
    // Load drivers
    response = http.get(`${BASE_URL}/api/fleet/drivers`, { headers });
    check(response, {
      'drivers load successful': (r) => r.status === 200,
    });
    errorRate.add(response.status >= 400);
    responseTime.add(response.timings.duration);
    requestCount.add(1);
  });
}

function testDispatcher(headers, companyId) {
  group('Dispatcher', function() {
    // Load loads data
    let response = http.get(`${BASE_URL}/api/performance/loads?page=1&limit=50`, { headers });
    check(response, {
      'loads data load successful': (r) => r.status === 200,
      'loads response time < 500ms': (r) => r.timings.duration < 500,
    });
    errorRate.add(response.status >= 400);
    responseTime.add(response.timings.duration);
    requestCount.add(1);
    
    // Load with filters
    response = http.get(`${BASE_URL}/api/performance/loads?status=assigned&page=1&limit=25`, { headers });
    check(response, {
      'filtered loads load successful': (r) => r.status === 200,
    });
    errorRate.add(response.status >= 400);
    responseTime.add(response.timings.duration);
    requestCount.add(1);
    
    // Create a test load (simulate dispatch activity)
    if (Math.random() < 0.1) { // 10% chance to create load
      const loadData = {
        loadNumber: `TEST-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        customerName: 'Test Customer',
        pickupLocation: 'Test Pickup Location',
        deliveryLocation: 'Test Delivery Location',
        rate: 1500.00,
        pickupDate: new Date().toISOString(),
        deliveryDate: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
      };
      
      response = http.post(`${BASE_URL}/api/loads`, JSON.stringify(loadData), { headers });
      check(response, {
        'load creation successful': (r) => r.status === 200 || r.status === 201,
      });
      errorRate.add(response.status >= 400);
      responseTime.add(response.timings.duration);
      requestCount.add(1);
    }
  });
}

function testDriver(headers, companyId) {
  group('Driver', function() {
    // Load driver-specific data
    let response = http.get(`${BASE_URL}/api/drivers/profile`, { headers });
    check(response, {
      'driver profile load successful': (r) => r.status === 200,
    });
    errorRate.add(response.status >= 400);
    responseTime.add(response.timings.duration);
    requestCount.add(1);
    
    // Load assigned loads
    response = http.get(`${BASE_URL}/api/drivers/loads`, { headers });
    check(response, {
      'driver loads load successful': (r) => r.status === 200,
    });
    errorRate.add(response.status >= 400);
    responseTime.add(response.timings.duration);
    requestCount.add(1);
    
    // Simulate location update
    if (Math.random() < 0.2) { // 20% chance to update location
      const locationData = {
        latitude: 40.7128 + (Math.random() - 0.5) * 0.1,
        longitude: -74.0060 + (Math.random() - 0.5) * 0.1,
        timestamp: new Date().toISOString()
      };
      
      response = http.post(`${BASE_URL}/api/drivers/location`, JSON.stringify(locationData), { headers });
      check(response, {
        'location update successful': (r) => r.status === 200,
      });
      errorRate.add(response.status >= 400);
      responseTime.add(response.timings.duration);
      requestCount.add(1);
    }
  });
}

export function teardown(data) {
  // Cleanup phase
  console.log('Load test completed');
  console.log(`Final metrics:`);
  console.log(`- Total requests: ${requestCount.count}`);
  console.log(`- Error rate: ${errorRate.rate * 100}%`);
  console.log(`- Average response time: ${responseTime.avg}ms`);
}

