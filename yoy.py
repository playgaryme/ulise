import requests
import base64
import random
import time
import logging
from seleniumbase import SB

# ====================== CONFIGURATION ======================
# Production-ready: Logging, constants, and easy tweaks
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Streamer (decoded once - no repeated base64 ops)
NAME_B64 = "YnJ1dGFsbGVz"
streamer = base64.b64decode(NAME_B64).decode("utf-8")
URL = f"https://www.twitch.tv/{streamer}"

# Sleep range (seconds) - tweak as needed
MIN_VIEW_TIME = 450
MAX_VIEW_TIME = 800

# Proxy (False = no proxy, or set to a string like "user:pass@host:port")
PROXY = False

# ====================== GEO DATA (fetched once) ======================
try:
    geo_response = requests.get("http://ip-api.com/json/", timeout=10)
    geo_response.raise_for_status()
    geo_data = geo_response.json()
    
    LAT = geo_data["lat"]
    LON = geo_data["lon"]
    TZ = geo_data["timezone"]
    
    logger.info(f"✅ Geo spoofing ready → Lat: {LAT}, Lon: {LON}, TZ: {TZ}")
except Exception as e:
    logger.error(f"❌ Failed to fetch geo data: {e}. Using fallback (no spoofing).")
    LAT = LON = 0.0
    TZ = "UTC"

# ====================== MAIN PRODUCTION LOOP ======================
while True:
    try:
        with SB(
            uc=True,                    # Undetectable mode
            locale="en",
            ad_block=True,
            chromium_arg="--disable-webgl",
            proxy=PROXY,
            # headless=False by default (visible for debugging; set True in prod if wanted)
        ) as main_driver:
            
            rnd_sleep = random.randint(MIN_VIEW_TIME, MAX_VIEW_TIME)
            
            # Load Twitch with geo/timezone spoofing via CDP
            main_driver.activate_cdp_mode(
                url=URL,
                tzone=TZ,
                geoloc=(LAT, LON)
            )
            main_driver.sleep(2)

            # Handle common cookie/consent popups
            if main_driver.is_element_present('button:contains("Accept")'):
                main_driver.cdp.click('button:contains("Accept")', timeout=4)
            main_driver.sleep(2)

            # Wait for page to settle and auto-play if needed
            main_driver.sleep(12)
            if main_driver.is_element_present('button:contains("Start Watching")'):
                main_driver.cdp.click('button:contains("Start Watching")', timeout=4)
                main_driver.sleep(10)

            # Extra consent check
            if main_driver.is_element_present('button:contains("Accept")'):
                main_driver.cdp.click('button:contains("Accept")', timeout=4)

            # Check if the stream is actually LIVE
            if main_driver.is_element_present("#live-channel-stream-information"):
                logger.info("🎥 LIVE stream detected - starting viewer session")

                # Extra consent inside live area
                if main_driver.is_element_present('button:contains("Accept")'):
                    main_driver.cdp.click('button:contains("Accept")', timeout=4)

                # === SECOND UNDETECTABLE VIEWER (as in original logic) ===
                extra_driver = main_driver.get_new_driver(undetectable=True)
                extra_driver.activate_cdp_mode(
                    url=URL,
                    tzone=TZ,
                    geoloc=(LAT, LON)
                )
                extra_driver.sleep(10)

                if extra_driver.is_element_present('button:contains("Start Watching")'):
                    extra_driver.cdp.click('button:contains("Start Watching")', timeout=4)
                    extra_driver.sleep(10)

                if extra_driver.is_element_present('button:contains("Accept")'):
                    extra_driver.cdp.click('button:contains("Accept")', timeout=4)

                # Keep BOTH viewers alive for the random duration (simulates real watching)
                main_driver.sleep(rnd_sleep)

                # Clean up extra driver safely (main driver is closed automatically by context manager)
                try:
                    extra_driver.quit()
                    logger.info(f"✅ Extra viewer closed after {rnd_sleep}s")
                except Exception as cleanup_err:
                    logger.warning(f"⚠️ Extra driver cleanup issue: {cleanup_err}")

                logger.info(f"✅ Session completed ({rnd_sleep}s view time). Restarting new session...")

            else:
                logger.info("⛔ No live stream detected. Exiting loop.")
                break

    except Exception as e:
        logger.error(f"🚨 Browser session crashed: {e}")
        logger.info("🔄 Retrying in 30 seconds...")
        time.sleep(30)
        continue  # Restart fresh browser instance
