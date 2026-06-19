import asyncio
from playwright.async_api import async_playwright
from PIL import Image
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        
        print("Navigating to localhost:3000")
        await page.goto("http://localhost:3000")
        
        # Wait for any login elements
        await asyncio.sleep(2)
        
        # Take login screenshot
        print("Taking login screenshot")
        await page.screenshot(path="docs/screenshots/raw_login.png")
        
        # Try to log in
        try:
            print("Attempting login...")
            await page.fill('input[type="email"]', 'demo@iip.gov')
            await page.fill('input[type="password"]', 'Demo1234!')
            await page.click('button[type="submit"], button:has-text("Login"), button:has-text("Sign in")')
            await asyncio.sleep(3)
        except Exception as e:
            print(f"Login steps failed or not needed: {e}")

        # Take dashboard screenshot
        print("Taking dashboard screenshot")
        await page.screenshot(path="docs/screenshots/raw_dashboard.png")
        
        # Click on something like "Cases"
        try:
            await page.click('a:has-text("Cases"), a:has-text("Evidence"), button:has-text("Cases")')
            await asyncio.sleep(2)
            print("Taking cases screenshot")
            await page.screenshot(path="docs/screenshots/raw_cases.png")
        except Exception as e:
            print(f"Cases navigation failed: {e}")

        await browser.close()
        
    print("Cropping and formatting screenshots...")
    for file in os.listdir("docs/screenshots"):
        if file.startswith("raw_") and file.endswith(".png"):
            img = Image.open(f"docs/screenshots/{file}")
            # Optional: crop top 50px if there's a browser bar, but headless has no browser bar.
            # We can crop to a nice aspect ratio or add rounded corners.
            # For now, just save it as the final image.
            final_name = file.replace("raw_", "")
            # Add a nice drop shadow or rounded corners if we want it "incredible looking"
            # Or just save it
            img.save(f"docs/screenshots/{final_name}", quality=95)
            print(f"Saved {final_name}")

if __name__ == "__main__":
    asyncio.run(main())
