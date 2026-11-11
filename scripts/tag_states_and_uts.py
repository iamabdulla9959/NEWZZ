import json
import sqlite3
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

INDIAN_STATES_AND_UTS = {
    # 28 States
    "Andhra Pradesh": ["andhra pradesh", "amaravati", "visakhapatnam", "vizag", "vijayawada", "tirupati", "guntur", "kurnool", "nellore"],
    "Arunachal Pradesh": ["arunachal pradesh", "itanagar", "tawang", "pasighat", "ziro"],
    "Assam": ["assam", "guwahati", "dispur", "dibrugarh", "silchar", "jorhat", "kaziranga", "brahmaputra"],
    "Bihar": ["bihar", "patna", "gaya", "bhagalpur", "muzaffarpur", "darbhanga", "purnia", "nalanda"],
    "Chhattisgarh": ["chhattisgarh", "raipur", "bilaspur", "durg", "bhilai", "bastar", "korba"],
    "Goa": ["goa", "panaji", "panjim", "margao", "vasco da gama", "calangute"],
    "Gujarat": ["gujarat", "gandhinagar", "ahmedabad", "surat", "vadodara", "baroda", "rajkot", "bhavnagar", "jamnagar", "kutch"],
    "Haryana": ["haryana", "gurugram", "gurgaon", "faridabad", "panipat", "ambala", "rohtak", "karnal", "hisar"],
    "Himachal Pradesh": ["himachal pradesh", "shimla", "dharamshala", "manali", "kullu", "mandi", "solan", "spiti"],
    "Jharkhand": ["jharkhand", "ranchi", "jamshedpur", "dhanbad", "bokaro", "deoghar", "hazaribagh"],
    "Karnataka": ["karnataka", "bengaluru", "bangalore", "mysuru", "mysore", "hubballi", "mangaluru", "mangalore", "belagavi"],
    "Kerala": ["kerala", "thiruvananthapuram", "trivandrum", "kochi", "cochin", "kozhikode", "calicut", "thrissur", "kannur", "wayanad", "kollam"],
    "Madhya Pradesh": ["madhya pradesh", "bhopal", "indore", "gwalior", "jabalpur", "ujjain", "rewa"],
    "Maharashtra": ["maharashtra", "mumbai", "pune", "nagpur", "nashik", "thane", "aurangabad", "sambhajinagar", "solapur", "kolhapur"],
    "Manipur": ["manipur", "imphal", "churachandpur", "kangpokpi", "bishnupur"],
    "Meghalaya": ["meghalaya", "shillong", "tura", "cherrapunji", "sohra"],
    "Mizoram": ["mizoram", "aizawl", "lunglei", "champhai"],
    "Nagaland": ["nagaland", "kohima", "dimapur", "mokokchung"],
    "Odisha": ["odisha", "orissa", "bhubaneswar", "cuttack", "rourkela", "puri", "sambalpur", "balasore"],
    "Punjab": ["punjab", "amritsar", "ludhiana", "jalandhar", "patiala", "bathinda", "mohali"],
    "Rajasthan": ["rajasthan", "jaipur", "jodhpur", "udaipur", "kota", "ajmer", "bikaner", "jaisalmer", "alwar"],
    "Sikkim": ["sikkim", "gangtok", "namchi", "pelling"],
    "Tamil Nadu": ["tamil nadu", "chennai", "madras", "coimbatore", "madurai", "tiruchirappalli", "trichy", "salem", "tirunelveli"],
    "Telangana": ["telangana", "hyderabad", "secunderabad", "warangal", "nizamabad", "karimnagar", "khammam", "revanth"],
    "Tripura": ["tripura", "agartala", "dharmanagar"],
    "Uttar Pradesh": ["uttar pradesh", "lucknow", "kanpur", "varanasi", "kashi", "prayagraj", "allahabad", "noida", "greater noida", "agra", "meerut", "ayodhya", "gorakhpur", "bareilly", "mathura"],
    "Uttarakhand": ["uttarakhand", "dehradun", "haridwar", "rishikesh", "nainital", "kedarnath", "badrinath", "roorkee"],
    "West Bengal": ["west bengal", "kolkata", "calcutta", "howrah", "durgapur", "siliguri", "asansol", "darjeeling"],
    
    # 8 Union Territories
    "Andaman and Nicobar Islands": ["andaman", "nicobar", "port blair"],
    "Chandigarh": ["chandigarh"],
    "Dadra and Nagar Haveli and Daman and Diu": ["dadra", "nagar haveli", "daman", "diu", "silvassa"],
    "Delhi": ["delhi", "new delhi", "ncr", "chawri bazar", "connaught place", "dwarka", "rohini"],
    "Jammu and Kashmir": ["jammu and kashmir", "jammu & kashmir", "j&k", "srinagar", "jammu", "anantnag", "baramulla", "kashmir"],
    "Ladakh": ["ladakh", "leh", "kargil"],
    "Lakshadweep": ["lakshadweep", "kavaratti"],
    "Puducherry": ["puducherry", "pondicherry", "karaikal", "mahe", "yanam"]
}

def detect_state(text):
    text_low = " " + text.lower() + " "
    for st, kws in INDIAN_STATES_AND_UTS.items():
        for kw in kws:
            pattern = r"[\s,.\-:\'\"\(\[\{]" + re.escape(kw) + r"[\s,.\-:\'\"\)\!\]\}]"
            if re.search(pattern, text_low):
                return st
    return None

def main():
    feed_path = Path("feed.json")
    if not feed_path.exists():
        print("feed.json not found")
        return

    with open(feed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    updated_count = 0
    state_breakdown = {}

    for it in items:
        headline = it.get("headline", "")
        summary = it.get("summary", "")
        full_text = f"{headline} {summary}"
        
        detected = detect_state(full_text)
        if detected:
            it["state"] = detected
            updated_count += 1
            state_breakdown[detected] = state_breakdown.get(detected, 0) + 1
        elif it.get("state") in INDIAN_STATES_AND_UTS:
            st = it["state"]
            state_breakdown[st] = state_breakdown.get(st, 0) + 1

    # Save to feed.json
    with open("feed.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Save to apps/api/app/static/feed.json
    static_feed = Path("apps/api/app/static/feed.json")
    if static_feed.parent.exists():
        with open(static_feed, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # Update SQLite newsreels.db
    db_path = Path("newsreels.db")
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        for it in items:
            if it.get("state"):
                cur.execute("UPDATE cards SET state = ? WHERE id = ?;", (it["state"], it["id"]))
        conn.commit()
        conn.close()
        print("newsreels.db updated with detected states.")

    print(f"Updated {updated_count} cards with detected Indian states/UTs.")
    print("Active State/UT Coverage:")
    for st, count in sorted(state_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"  {st}: {count} stories")

if __name__ == "__main__":
    main()

