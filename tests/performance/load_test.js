import http from 'k6/http';
import { check, sleep } from 'k6';

// Read target URL from environment variable or default to local dev server
const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

export const options = {
    // Stage 1: Ramp up to 50 users over 30s
    // Stage 2: Stay at 50 users for 1m
    // Stage 3: Ramp down to 0 users over 30s
    stages: [
        { duration: '30s', target: 50 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 0 },
    ],
    thresholds: {
        // 95% of requests must complete below 500ms
        http_req_duration: ['p(95)<500'],
        // Error rate must be less than 1%
        http_req_failed: ['rate<0.01'],
    },
};

export default function () {
    // 1. Liveness Check
    const healthRes = http.get(`${BASE_URL}/health`);
    check(healthRes, {
        'health is status 200': (r) => r.status === 200,
        'health returns ok': (r) => r.json('status') === 'ok',
    });

    // 2. Mock API Classification Request
    // In a real load test, we'd use dynamic data or a CSV file.
    // Here we test a core sync endpoint hitting the DB and Model cache.
    const payload = JSON.stringify({
        text: 'UBER TRIP SAN FRANCISCO CA',
        amount: 25.50
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
            'X-Request-ID': `k6-test-${__VU}-${__ITER}`,
        },
    };

    const classifyRes = http.post(`${BASE_URL}/api/v1/categories/classify`, payload, params);
    
    // We expect 401 Unauthorized if auth is enforced, or 200/429.
    // We'll relax the check just to ensure it's not a 500 server error since
    // auth tokens aren't passed in this basic script yet.
    check(classifyRes, {
        'classify is not 5xx': (r) => r.status < 500,
    });

    sleep(1); // Wait 1 second between iterations per VU
}
