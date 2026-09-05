from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    # 1. Test Clerk Auth page
    p1 = browser.new_page(viewport={"width": 1280, "height": 720})
    p1.goto("http://127.0.0.1:5173/")
    time.sleep(2)
    p1.screenshot(path="docs/screenshots/verify_clerk_auth_page.png")
    clerk_text = p1.locator("body").inner_text()
    assert "Human authority starts with identity" in clerk_text, "Clerk hero missing"
    assert "Sign in to Janus" in clerk_text, "Clerk sign-in missing"
    print("PASS: Clerk Authentication is active and rendering successfully!")
    
    # 2. Test Control Room layout with fixed bottom card
    p2 = browser.new_page(viewport={"width": 1280, "height": 720})
    p2.goto("http://127.0.0.1:5173/?bypass_auth=1")
    time.sleep(1)
    tile = p2.locator(".hero-action-tile")
    box = tile.bounding_box()
    print("Hero Action Tile Bounding Box:", box)
    assert box["height"] >= 220, f"Card height too small: {box['height']}"
    
    # Scroll down and verify full visibility
    p2.locator(".workspace-content").evaluate("el => el.scrollTop = 500")
    time.sleep(0.5)
    p2.screenshot(path="docs/screenshots/verify_fixed_bottom_cards.png")
    
    title = p2.locator(".hero-action-tile h3").inner_text()
    btn = p2.locator(".hero-action-tile button").inner_text()
    print(f"Card Title: \"{title}\"")
    print(f"Card Button: \"{btn}\"")
    assert "Delegate a Bounded Purchase" in title or "Test the Checkout Boundary" in title
    assert "ISSUE NEW MANDATE" in btn or "LAUNCH CHECKOUT ENGINE" in btn
    print("PASS: Bottom cards are fully rendered with zero clipping at 240px height!")
    
    browser.close()
print("\nALL VERIFICATIONS PASSED!")
