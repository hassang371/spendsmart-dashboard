import { test, expect } from '@playwright/test';

test.describe('Authentication Flows', () => {
  test('Login page renders correctly', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
    await expect(page.getByPlaceholder(/email/i)).toBeVisible();
    await expect(page.getByPlaceholder(/password/i)).toBeVisible();
  });

  test('Signup page renders correctly', async ({ page }) => {
    await page.goto('/signup');
    await expect(page.getByRole('heading', { name: 'Create Account' })).toBeVisible();
    await expect(page.getByPlaceholder(/name@example.com/i)).toBeVisible();
    await expect(page.getByPlaceholder(/password/i)).toBeVisible();
  });

  test('Dashboard redirects to login when unauthenticated', async ({ page }) => {
    await page.goto('/dashboard');
    // Should be redirected back to the login page or a designated auth page
    await expect(page).toHaveURL(/.*login/);
  });
});
