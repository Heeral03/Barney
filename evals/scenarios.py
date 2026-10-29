"""Hand-written shopping scenarios with fixed listings, so the whole graph can be run without a search API.

The brands are invented. Each catalog mixes good listings (`ok`) with the traps Barney is supposed to avoid (`trap`):
an old model that is cheapest, the wrong connector, an accessory instead of the product, a few-review 4.9, the wrong
audience, a junk price. Model years are relative to today, so the dataset does not go stale.

`persona` answers the questionnaire if Barney asks one: the first option whose text contains a keyword is tapped.
"""
from datetime import date

NOW, OLD = date.today().year, date.today().year - 4


def L(id, title, price, rating, count, seller="Amazon.in"):
    return {"id": id, "title": title, "price_inr": price, "rating": rating, "rating_count": count, "seller": seller}


SCENARIOS = [
    {
        "id": "headphones-usbc",
        "message": "I want wireless headphones that charge over USB-C, under ₹5,000",
        "persona": ["over-ear", "usb-c", "type-c", "wireless", "bluetooth", "5,000", "noise"],
        "ok": {"h1", "h2"}, "trap": {"h3", "h4", "h5", "h6", "h7"},
        "catalog": [
            L("h1", f"Auralis Pulse 3 Wireless Bluetooth Headphones, USB-C Fast Charge, ANC ({NOW})", 3999, 4.4, 5200),
            L("h2", f"Voxa Studio Wireless Over-Ear Headphones Type-C Charging {NOW - 1} Edition", 4499, 4.5, 2300, "Flipkart"),
            L("h3", f"Auralis Beat Wireless Headphones Micro USB Charging ({OLD} Model)", 1499, 4.1, 18000),
            L("h4", f"Voxa Lite Wireless Headphones with Lightning Charging Port {OLD}", 1799, 4.0, 6000, "Flipkart"),
            L("h5", f"Replacement Ear Cushion Pads for Auralis Pulse Headphones", 499, 4.3, 900),
            L("h6", "NoName Bluetooth Headphone Super Bass", 199, None, 0, "QuickDeals99"),
            L("h7", f"Zentro Elite ANC Wireless Headphones USB-C ({NOW})", 6999, 4.7, 800, "Flipkart"),
        ],
    },
    {
        "id": "laptop-coding",
        "message": "Best laptop for programming under ₹90,000",
        "persona": ["16", "ssd", "windows", "portable", "coding", "90,000", "programming"],
        "ok": {"l1", "l2"}, "trap": {"l3", "l4", "l5", "l6"},
        "catalog": [
            L("l1", f"Nexa Book Pro 14 ({NOW}) Intel Core Ultra 7, 16GB RAM, 512GB SSD, Windows 11", 84990, 4.4, 1900),
            L("l2", f"Orbit Slim 15 {NOW - 1} AMD Ryzen 7, 16GB RAM, 1TB SSD, 15.6 inch", 79990, 4.3, 2600, "Flipkart"),
            L("l3", f"Nexa Book 14 ({OLD}) Intel Core i5 11th Gen, 8GB RAM, 512GB SSD", 42990, 4.2, 12000),
            L("l4", f"Orbit Slim 15 {OLD} Ryzen 5 5500U 8GB 256GB", 38990, 4.0, 9000, "Flipkart"),
            L("l5", f"Nexa Book Ultra 16 ({NOW}) Core Ultra 9, 32GB RAM, 1TB SSD, OLED", 139990, 4.6, 400),
            L("l6", f"Laptop Sleeve Bag 15.6 inch for Nexa and Orbit laptops", 799, 4.4, 5000),
        ],
    },
    {
        "id": "phone-25k",
        "message": "Looking for a good smartphone under ₹25,000 with a great camera",
        "persona": ["camera", "android", "5g", "25,000", "battery", "usb-c"],
        "ok": {"p1", "p2"}, "trap": {"p3", "p4", "p5", "p6"},
        "catalog": [
            L("p1", f"Kestrel X5 5G ({NOW}) 8GB RAM 256GB, 50MP OIS Camera, 5000mAh", 22999, 4.3, 3100),
            L("p2", f"Lumen Nova 3 5G {NOW - 1} 8GB+128GB 108MP Camera AMOLED", 19999, 4.2, 5400, "Flipkart"),
            L("p3", f"Kestrel X2 4G ({OLD}) 4GB RAM 64GB 13MP Camera", 8999, 4.0, 40000),
            L("p4", f"Lumen Spark ({OLD}) 6GB 128GB Dual Camera", 10499, 4.1, 21000, "Flipkart"),
            L("p5", "Tempered Glass Screen Protector for Kestrel X5 (Pack of 3)", 299, 4.2, 7000),
            L("p6", f"Kestrel Max Pro 5G ({NOW}) 12GB 512GB 200MP", 44999, 4.6, 900),
        ],
    },
    {
        "id": "running-shoes-women",
        "message": "I need running shoes for women under ₹5,000",
        "persona": ["road", "women", "cushion", "daily", "5,000", "running"],
        "ok": {"s1", "s2", "s6", "s7"}, "trap": {"s3", "s4", "s5"},
        "catalog": [
            L("s1", f"Strideway Glide 4 Women's Running Shoes ({NOW}) Cushioned Daily Trainer", 3999, 4.5, 1400),
            L("s2", f"Pacer Flex Women Running Shoes {NOW - 1} Lightweight Road", 2999, 4.3, 2200, "Flipkart"),
            L("s3", f"Strideway Glide 4 Men's Running Shoes ({NOW})", 3899, 4.6, 3000),
            L("s4", "Pacer Kids Running Shoes Boys and Girls", 1299, 4.2, 800, "Flipkart"),
            L("s5", f"Strideway Women's Running Shoes ({OLD} Model)", 1799, 4.1, 9000),
            L("s6", f"Dashline Aero Women's Running Shoes ({NOW}) Breathable Mesh", 3499, 4.4, 1100),
            L("s7", f"Pacer Swift Women Running Shoes {NOW - 1} Cushioned Sole", 2799, 4.2, 1700, "Flipkart"),
        ],
    },
    {
        "id": "shampoo-oily-dandruff",
        "message": "I need a shampoo for oily scalp and dandruff, budget around ₹600",
        "persona": ["dandruff", "oily", "600", "anti", "sulphate", "scalp"],
        "ok": {"c1", "c2"}, "trap": {"c3", "c4", "c5"},
        "catalog": [
            L("c1", "Purelle Anti-Dandruff Shampoo for Oily Scalp with Zinc Pyrithione 340ml", 449, 4.4, 6200),
            L("c2", "Verda Scalp Care Anti Dandruff Shampoo Tea Tree Oil Oily Hair 250ml", 549, 4.3, 3100, "Flipkart"),
            L("c3", "Silkroot Moisturising Shampoo for Dry and Frizzy Hair 400ml", 399, 4.5, 8000),
            L("c4", "Purelle Gentle Baby Shampoo Tear Free 200ml", 249, 4.6, 5000),
            L("c5", "Verda Hair Growth Serum Anti Hair Fall 100ml", 599, 4.2, 1200, "Flipkart"),
        ],
    },
    {
        "id": "backpack-laptop",
        "message": "A backpack for my 15.6 inch laptop for daily office use, under ₹2,500",
        "persona": ["15.6", "water", "office", "2,500", "laptop"],
        "ok": {"b1", "b2"}, "trap": {"b3", "b4", "b5"},
        "catalog": [
            L("b1", "Carrion Office Laptop Backpack fits up to 15.6 inch, Water Resistant, 30L", 1799, 4.4, 7600),
            L("b2", "Trekline Business Backpack 15.6 inch Laptop Compartment USB Port", 1999, 4.3, 4100, "Flipkart"),
            L("b3", "Carrion Mini Sling Bag for Tablets up to 10 inch", 699, 4.3, 3000),
            L("b4", "Trekline Waterproof Rain Cover for Backpacks", 299, 4.5, 2000, "Flipkart"),
            L("b5", "Carrion Premium Leather Laptop Backpack 15.6 inch", 6499, 4.6, 500),
        ],
    },
    {
        "id": "smartwatch-android",
        "message": "Smartwatch for my Android phone under ₹8,000 with good battery life",
        "persona": ["android", "battery", "fitness", "8,000", "gps"],
        "ok": {"w1", "w2"}, "trap": {"w3", "w4", "w5"},
        "catalog": [
            L("w1", f"Tempo Fit 2 Smartwatch ({NOW}) AMOLED GPS 14-Day Battery Android and iOS", 6999, 4.3, 2100),
            L("w2", f"Chrono Active {NOW - 1} Smart Watch Bluetooth Calling 10 Day Battery Android", 3499, 4.1, 9000, "Flipkart"),
            L("w3", f"Tempo Fit ({OLD}) Smart Band Basic 3 Day Battery", 1299, 4.0, 30000),
            L("w4", "Tempo Fit Strap Replacement Silicone Band", 399, 4.4, 1500),
            L("w5", f"Chrono Pro iOS-only Smartwatch ({NOW}) Works with iPhone only", 7499, 4.5, 700, "Flipkart"),
        ],
    },
    {
        "id": "refurb-laptop",
        "message": "I want a refurbished laptop for college under ₹30,000, older models are fine",
        "persona": ["refurbished", "college", "30,000", "ssd"],
        "ok": {"r1", "r2", "r3"}, "trap": {"r4", "r5"},
        "catalog": [
            L("r1", f"Nexa Book 14 ({OLD}) Refurbished Core i5 8GB 256GB SSD Renewed", 27990, 4.1, 3500),
            L("r2", f"Orbit Slim 15 {OLD} Renewed Ryzen 5 8GB 512GB SSD", 29490, 4.0, 2200, "Flipkart"),
            L("r3", f"Nexa Book 13 ({OLD - 1}) Refurbished Core i5 8GB 256GB", 22990, 3.9, 1800),
            L("r4", f"Nexa Book Pro 14 ({NOW}) Brand New Core Ultra 7 16GB", 84990, 4.4, 1900),
            L("r5", "Laptop Charger Adapter 65W Universal Compatible", 899, 4.2, 6000),
        ],
    },
]
