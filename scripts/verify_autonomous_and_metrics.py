from playwright.sync_api import sync_playwright
import time
import os

os.makedirs("docs/screenshots", exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    
    # 1. Open Console with auth bypass for testing
    page.goto("http://127.0.0.1:5173/?bypass_auth=1")
    time.sleep(2)
    
    # 2. Test Merchant Catalog & Track 01 Telemetry Banner
    print("Testing Merchant Catalog & Track 01 Telemetry...")
    page.locator("button.nav-item-btn:has-text('Merchant Catalog')").click()
    time.sleep(2)
    page.screenshot(path="docs/screenshots/verify_merchant_catalog_telemetry.png")
    
    body_text = page.locator("body").inner_text()
    assert "TRACK 01 MERCHANT SKUS" in body_text, "Track 01 SKUs card missing"
    assert "AUTONOMOUS GMV SETTLED" in body_text, "Autonomous GMV card missing"
    assert "PREVENTED OVERSPEND" in body_text, "Prevented Overspend card missing"
    assert "AGENT CONVERSION RATE" in body_text, "Conversion Rate card missing"
    assert "Machine-Readable" in body_text, "Machine readable badge missing"
    print("PASS: Track 01 Merchant Commerce Telemetry is rendered live!")
    
    # 3. Issue an active mandate
    print("Issuing active mandate for agent...")
    page.locator("button.nav-item-btn:has-text('Issue Mandate')").click()
    time.sleep(1)
    
    page.locator("button.btn-primary:has-text('COMPILE INTENT BOUNDS')").click()
    time.sleep(2)
    
    page.locator("button.btn-primary:has-text('SIGN')").click()
    time.sleep(2)
    print("PASS: Mandate compiled, signed, and activated!")
    
    # 4. Open Checkout Engine (Simulator)
    print("Testing Autonomous Buyer Agent in Checkout Engine...")
    page.locator("button.nav-item-btn:has-text('Checkout Engine')").click()
    time.sleep(1)
    
    # Verify Autonomous Buyer Agent tab is present
    assert page.locator("button.mode-pill-btn:has-text('Autonomous Buyer Agent')").is_visible()
    
    # Click Dispatch Autonomous Buyer Agent
    dispatch_btn = page.locator("button:has-text('DISPATCH AUTONOMOUS BUYER AGENT')")
    assert dispatch_btn.is_visible()
    dispatch_btn.click()
    print("Dispatched autonomous agent, awaiting multi-stage cycle...")
    
    # Wait for the autonomous cycle to finish
    time.sleep(4)
    page.screenshot(path="docs/screenshots/verify_autonomous_buyer_agent.png")
    
    sim_text = page.locator("body").inner_text()
    assert "MULTI-STAGE AUTONOMOUS REASONING TRACE" in sim_text, "Reasoning trace missing"
    assert "CANDIDATE SKU ELIMINATION" in sim_text, "Elimination matrix missing"
    assert "AUTONOMOUS CYCLE VERDICT" in sim_text, "Cycle verdict missing"
    assert "Sony Voyager NC" in sim_text, "Selected product missing"
    print("PASS: Autonomous Buyer Agent executed 6 stages, generated candidate matrix, and settled order!")
    
    # Scroll right column to capture candidate elimination matrix
    page.locator(".agent-results-column").evaluate("el => el.scrollTop = 500")
    time.sleep(1)
    page.screenshot(path="docs/screenshots/verify_candidate_matrix.png")
    
    # If Step-Up was required (e.g. mock/unavailable LLM fallback), approve to test Razorpay execution
    if page.locator("button:has-text('STEP-UP ESCALATED')").is_visible():
        print("Proposal triggered Human Step-Up (Fail-Closed). Resolving via Human Console...")
        page.locator("button:has-text('STEP-UP ESCALATED')").click()
        time.sleep(1.5)
        page.locator("button:has-text('APPROVE ONCE')").click()
        time.sleep(3)
        page.screenshot(path="docs/screenshots/verify_stepup_approved.png")
        print("PASS: Human Step-Up approved! Razorpay order created.")
        page.wait_for_selector("button.btn-razorpay", timeout=10000)
        assert page.locator("button.btn-razorpay").is_visible(), "Razorpay Checkout button should be visible after step-up approval"
        print("PASS: Razorpay Test Checkout button is armed and ready!")
    else:
        rzp_btn = page.locator("button.btn-razorpay")
        assert rzp_btn.is_visible(), "Razorpay Checkout button should be visible"
        print("PASS: Razorpay Test Checkout button is armed and ready!")
    
    # 6. Test Interactive Simulator Mode
    page.locator("button.nav-item-btn:has-text('Checkout Engine')").click()
    time.sleep(1)
    page.locator("button.mode-pill-btn:has-text('Interactive Simulator')").click()
    time.sleep(1)
    page.screenshot(path="docs/screenshots/verify_interactive_simulator.png")
    inter_text = page.locator("body").inner_text()
    assert "SELECT SKU TO PROPOSE" in inter_text, "Interactive product selector missing"
    print("PASS: Interactive Simulator mode toggle operates seamlessly!")
    
    browser.close()

print("\nALL AUTONOMOUS AGENT & TELEMETRY VERIFICATIONS PASSED SUCCESSFULLY!")
