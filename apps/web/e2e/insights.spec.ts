import { AxeBuilder } from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

/**
 * `/insights` accessibility + smoke test.
 *
 * Skips automatically when no Supabase test-user JWT is available locally.
 * Local devs with a configured `.env.local` containing a real session will
 * exercise the populated path; otherwise the test is skipped (the Playwright
 * suite still passes).
 *
 * To run locally:
 *   1. Sign in via the dev login form.
 *   2. Copy the storageState file path into PLAYWRIGHT_AUTH_STATE.
 *   3. Re-run `npx playwright test apps/web/e2e/insights.spec.ts`.
 *
 * Refs:
 *   docs/features/011-ai-insights-page.md §Testing Strategy → Contract tests
 */

const AUTH_STATE_PATH = process.env.PLAYWRIGHT_AUTH_STATE;

test.describe('/insights accessibility smoke', () => {
  test.skip(!AUTH_STATE_PATH, 'No PLAYWRIGHT_AUTH_STATE — skip authenticated /insights e2e');

  test.use({ storageState: AUTH_STATE_PATH });

  test('main components render and axe reports no serious+ violations', async ({ page }) => {
    await page.goto('/insights');
    await expect(page.getByTestId('insights-page')).toBeVisible();

    // Seven required components per LLD 011 §Success Criteria.
    await expect(page.getByTestId('balance-forecast-chart')).toBeVisible();
    await expect(page.getByTestId('safe-to-spend-card')).toBeVisible();
    await expect(page.getByTestId('month-end-snapshot')).toBeVisible();
    await expect(page.getByTestId('confidence-badge')).toBeVisible();
    await expect(page.getByTestId('primary-drivers')).toBeVisible();
    // ScenarioImpactCard renders one of two testids depending on intent state.
    const scenarioVisible =
      (await page
        .getByTestId('scenario-impact-card')
        .isVisible()
        .catch(() => false)) ||
      (await page
        .getByTestId('scenario-impact-empty')
        .isVisible()
        .catch(() => false));
    expect(scenarioVisible).toBe(true);
    await expect(page.getByTestId('add-plan-trigger')).toBeVisible();

    // AddPlanModal opens.
    await page.getByTestId('add-plan-trigger').click();
    await expect(page.getByTestId('add-plan-modal')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('add-plan-modal')).not.toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const seriousOrAbove = results.violations.filter(
      v => v.impact === 'serious' || v.impact === 'critical'
    );
    expect(seriousOrAbove, JSON.stringify(seriousOrAbove, null, 2)).toEqual([]);
  });
});
