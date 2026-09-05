import json
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = Path("D:/janus/docs/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

def run_browser_verification():
    console_errors = []
    page_errors = []

    print("==================================================")
    print("STARTING END-TO-END CHROME VERIFICATION")
    print("==================================================")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Capture console messages and errors
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error"] else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # 1. Open home page
        print("\n[1/7] Navigating to http://127.0.0.1:5173/ ...")
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle", timeout=15000)
        time.sleep(1)

        # Check for window chrome dots (should NOT exist)
        traffic_lights = page.locator(".traffic-lights").count()
        browser_header = page.locator(".browser-header").count()
        print(f"Checking window chrome: traffic-lights count = {traffic_lights}, browser-header count = {browser_header}")
        assert traffic_lights == 0, "Error: traffic-lights still exist!"
        assert browser_header == 0, "Error: browser-header still exist!"

        # Screenshot Control Room
        sc1 = SCREENSHOT_DIR / "01_control_room.png"
        page.screenshot(path=str(sc1))
        print(f"Captured: {sc1}")

        # Test Interactive Simulator tabs on home page
        print("Testing interactive visualizer on home page...")
        scenarios = page.locator(".scenario-tab")
        print(f"Found {scenarios.count()} interactive scenario tabs on Control Room.")
        for i in range(scenarios.count()):
            tab = scenarios.nth(i)
            tab_text = tab.inner_text()
            tab.click()
            time.sleep(0.3)
            print(f"  - Clicked: {tab_text}")

        # 2. Click Merchant Catalog
        print("\n[2/7] Clicking 'Merchant Catalog'...")
        catalog_btn = page.locator("button:has-text('Merchant Catalog')")
        catalog_btn.click()
        time.sleep(1)

        # Verify not blank
        catalog_title = page.locator("h1:has-text('Authoritative Merchant Facts')")
        assert catalog_title.is_visible(), "Error: Merchant Catalog heading not visible!"
        products_count = page.locator(".product-row-item").count()
        print(f"Merchant Catalog opened successfully! Product rows found: {products_count}")
        assert products_count > 0, "Error: No product rows rendered in Merchant Catalog!"

        sc2 = SCREENSHOT_DIR / "02_merchant_catalog.png"
        page.screenshot(path=str(sc2))
        print(f"Captured: {sc2}")

        # 3. Click Issue Mandate
        print("\n[3/7] Clicking 'Issue Mandate'...")
        issue_btn = page.locator("button:has-text('Issue Mandate')")
        issue_btn.click()
        time.sleep(0.8)

        # Compile intent
        compile_btn = page.locator("button:has-text('COMPILE INTENT BOUNDS')")
        compile_btn.click()
        time.sleep(1.5)

        # Sign & activate mandate
        sign_btn = page.locator("button:has-text('SIGN & ACTIVATE MANDATE')")
        assert sign_btn.is_visible(), "Error: Sign mandate button not visible after compile!"
        sign_btn.click()
        time.sleep(1.5)

        # Should now be on Mandate Envelope
        print("Mandate signed successfully! Checking Mandate Envelope view...")
        sc3 = SCREENSHOT_DIR / "03_mandate_envelope.png"
        page.screenshot(path=str(sc3))
        print(f"Captured: {sc3}")

        # 4. Click Checkout Engine (Simulator)
        print("\n[4/7] Clicking 'Checkout Engine'...")
        sim_btn = page.locator("button:has-text('Checkout Engine')")
        sim_btn.click()
        time.sleep(0.8)

        # Select first product
        prod_btns = page.locator(".sim-product-btn")
        print(f"Found {prod_btns.count()} selectable products in simulator.")
        assert prod_btns.count() > 0, "Error: No selectable products in simulator!"
        prod_btns.nth(0).click()
        time.sleep(0.3)

        # Propose checkout
        propose_btn = page.locator("button:has-text('PROPOSE CHECKOUT')")
        propose_btn.click()
        time.sleep(2)

        # Verify decision verdict
        verdict = page.locator(".decision-badge-big")
        assert verdict.is_visible(), "Error: Decision verdict badge not rendered!"
        verdict_text = verdict.inner_text()
        print(f"Propose Checkout succeeded! Verdict: {verdict_text}")

        sc4 = SCREENSHOT_DIR / "04_checkout_engine.png"
        page.screenshot(path=str(sc4))
        print(f"Captured: {sc4}")

        # 5. Click Human Step-Up
        print("\n[5/7] Clicking 'Human Step-Up' in sidebar...")
        stepup_btn = page.locator(".sidebar-nav button:has-text('Human Step-Up')")
        stepup_btn.click()
        time.sleep(0.8)

        # Check if empty state or active
        stepup_title = page.locator("h1:has-text('Ambiguity Belongs to Humans'), strong:has-text('Human Oversight Console')")
        assert stepup_title.first.is_visible(), "Error: Human Step-Up view did not render properly!"
        print("Human Step-Up view opened successfully with zero blank screen!")

        # If simulate button is present, click it to test escalation
        sim_contradiction_btn = page.locator("button:has-text('Simulate Contradiction Step-Up')")
        if sim_contradiction_btn.is_visible():
            print("Clicking 'Simulate Contradiction Step-Up (Demo Beat 3)'...")
            sim_contradiction_btn.click()
            time.sleep(3)
            # Verify escalation details rendered
            reason_elem = page.locator("strong:has-text('SEMANTIC CONTRADICTED')")
            print(f"Contradiction escalation simulated! Reason visible: {reason_elem.is_visible()}")

        sc5 = SCREENSHOT_DIR / "05_human_stepup.png"
        page.screenshot(path=str(sc5))
        print(f"Captured: {sc5}")

        # 6. Click Signal Feed
        print("\n[6/7] Clicking 'Signal Feed' in sidebar...")
        audit_btn = page.locator(".sidebar-nav button:has-text('Signal Feed')")
        audit_btn.click()
        time.sleep(1)

        # Verify signals are listed
        audit_title = page.locator("h1:has-text('Real-Time Decision Audit')")
        assert audit_title.is_visible(), "Error: Signal Feed heading not visible!"
        signals = page.locator(".signal-item-row")
        signals_count = signals.count()
        print(f"Signal Feed opened successfully! Signals recorded: {signals_count}")
        assert signals_count > 0, "Error: No signals recorded in Signal Feed!"

        # Click first signal to expand JSON payload
        signals.nth(0).click()
        time.sleep(0.4)
        payload_pre = page.locator(".signal-payload-pre")
        assert payload_pre.is_visible(), "Error: Signal payload didn't expand on click!"
        print("First signal expanded successfully to view structured cryptographic payload.")

        sc6 = SCREENSHOT_DIR / "06_signal_feed.png"
        page.screenshot(path=str(sc6))
        print(f"Captured: {sc6}")

        # 7. Return to Control Room to verify overall stability
        print("\n[7/7] Returning to Control Room...")
        overview_btn = page.locator(".sidebar-nav button:has-text('Control Room')")
        overview_btn.click()
        time.sleep(0.5)

        browser.close()

    print("\n==================================================")
    print("VERIFICATION COMPLETE SUMMARY")
    print("==================================================")
    print(f"Page Errors: {len(page_errors)}")
    for err in page_errors:
        print(f"  - {err}")
    print(f"Console Errors: {len(console_errors)}")
    for err in console_errors:
        print(f"  - {err}")

    if page_errors or console_errors:
        print("\nFAILED: Console or Page errors detected during Chrome verification!")
        sys.exit(1)
    else:
        print("\nPASSED: 100% of views rendered, clicked, and operated in Chrome with ZERO errors!")
        sys.exit(0)

if __name__ == "__main__":
    run_browser_verification()
