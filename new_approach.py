from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pandas as pd
import time
import re

options = webdriver.ChromeOptions()
options.add_argument("--headless")  #background running
options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(options=options)

base_url = "https://www.city24.ee/en/real-estate-search/apartments-for-sale/tallinn/id=181-parish/pg="
pages_to_scrape = 84
wait_time = 5  #wait for page loading


def clean_price(price_text): #numeric values extraction
    if not price_text or price_text == "N/A":
        return "N/A"

    # Remove all non-numeric characters except digits and decimal separators
    cleaned = re.sub(r"[^\d,.]", "", price_text.replace(" ", ""))  # Remove thin spaces
    cleaned = cleaned.replace(",", ".")  # Convert European decimal format if needed

    try:
        return float(cleaned) if "." in cleaned else int(cleaned)
    except ValueError:
        return "N/A"


def scrape_listing(listing): #flexible selectors for listings
    try:
        address = listing.find_element(
            By.XPATH, ".//*[contains(@class, 'address') or contains(@class, 'heading')]"
        ).text.strip()
        try:
            price_main_text = listing.find_element(
                By.XPATH, ".//*[contains(@class, 'object-price__main-price') or contains(@class, 'cost')]"
            ).text.strip()
            price_main = clean_price(price_main_text)
        except NoSuchElementException:
            price_main = "N/A"

        try:
            price_meter_text = listing.find_element(
                By.XPATH, ".//*[contains(@class, 'object-price__m2-price') or contains(@class, 'cost')]"
            ).text.strip()
            price_meter = clean_price(price_meter_text)
        except NoSuchElementException:
            price_meter = "N/A"

        area = listing.find_element(
            By.XPATH, ".//*[contains(@class, 'object_area') or contains(@class, 'area')]"
        ).text.strip()

        link = listing.find_element(
            By.XPATH, ".//a[contains(@href, '/en/')]"
        ).get_attribute("href")


        features = {
            'size': None, #change later
            'rooms': "N/A",
            'floor': "N/A",
            'year': "N/A"
        }

        try:
            features_container = listing.find_element(
                By.XPATH, ".//div[contains(@class, 'object__features')]//ul[contains(@class, 'object__main-features')]"
            )
            feature_items = features_container.find_elements(By.TAG_NAME, "li")

            # size of the apartment is always there(afaik)
            if feature_items:
                size_text = feature_items[0].text.strip()
                features['size'] = size_text.replace('m²', '').strip()  # Remove m²

                #some features on website are within unordered list within another list
                #they are differentiated by the icon
                for item in feature_items[1:]:
                    try:
                        icon = item.find_element(By.TAG_NAME, "span").get_attribute("class")

                        if 'icon-door' in icon or 'icon-rooms' in icon:
                            features['rooms'] = item.text.strip()
                        elif 'icon-stairs' in icon or 'icon-floor' in icon:
                            features['floor'] = item.text.strip()
                        elif 'icon-bricks' in icon or 'icon-year' in icon:
                            features['year'] = item.text.strip()

                    except NoSuchElementException:
                        continue

        except NoSuchElementException:
            pass

        #if features['size'] is None:
            #features['size'] = "N/A"

        return {
            "Address": address,
            "General Price": price_main,
            "Price/m": price_meter,
            "Area": area,
            "Size": features['size'],
            "Rooms": features['rooms'],
            "Floor": features['floor'],
            "Year": features['year'],
            "Link": link
        }

    except Exception as e:
        print(f"Error scraping listing: {e}")
        return None


#main loop
all_listings = []
for page in range(1, pages_to_scrape + 1):
    print(f"Scraping page {page}...")
    url = base_url + str(page)
    driver.get(url)

    try:
        # waitin until it loads
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((
                By.XPATH, "//*[contains(@class, 'object-wrapper') or contains(@class, 'object_info')]"
            ))
        )

        #all the apartments sold are structured within ibject-wrappers,
        #get the object wrappers and search for key parameters out of them
        listings = driver.find_elements(
            By.XPATH, "//*[contains(@class, 'object-wrapper') or contains(@class, 'object_info')]"
        )

        #process each
        for listing in listings:
            listing_data = scrape_listing(listing)
            if listing_data:
                all_listings.append(listing_data)

    except TimeoutException:
        print(f"Timed out waiting for page {page}")
    except Exception as e:
        print(f"Error on page {page}: {e}")

    time.sleep(2)  #wait between requests

#save
if all_listings:
    df = pd.DataFrame(all_listings)
    df.to_csv("city24_apartments.csv", index=False)
    print(f"Successfully saved {len(all_listings)} listings to city24_apartments.csv")
else:
    print("No listings scraped.")

driver.quit()
