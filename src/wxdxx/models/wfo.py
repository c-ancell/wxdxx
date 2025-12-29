"""Models for WFO text products."""

from datetime import datetime

from .base import BaseProduct


# NWS product type abbreviations and their meanings
PRODUCT_ABBREVIATIONS = {
    # Forecast products
    "AFD": "Area Forecast Discussion",
    "ZFP": "Zone Forecast Product",
    "NOW": "Short Term Forecast",
    # Hazard products
    "HWO": "Hazardous Weather Outlook",
    "SPS": "Special Weather Statement",
    # Watch/warning products
    "SVS": "Severe Weather Statement",
    "SVR": "Severe Thunderstorm Warning",
    "TOR": "Tornado Warning",
    "FFW": "Flash Flood Warning",
    "WSW": "Winter Storm Warning",
    # SPC products
    "MCD": "Mesoscale Discussion",
    "WWA": "Watch/Warning/Advisory",
    "PTS": "Probabilistic Outlook Points",
}

# Common product types to display in the sidebar
DEFAULT_PRODUCT_TYPES = ["AFD", "HWO", "SPS", "NOW", "ZFP"]

# Major cities in each WFO's coverage area
# Used to show representative cities when NWS API doesn't provide location data
WFO_CITIES: dict[str, list[str]] = {
    # Central Region
    "ABR": ["Aberdeen, SD", "Watertown, SD"],
    "APX": ["Gaylord, MI", "Traverse City, MI", "Alpena, MI"],
    "ARX": ["La Crosse, WI", "Rochester, MN", "Winona, MN"],
    "BIS": ["Bismarck, ND", "Minot, ND", "Dickinson, ND"],
    "BOU": ["Denver, CO", "Boulder, CO", "Fort Collins, CO"],
    "CYS": ["Cheyenne, WY", "Laramie, WY", "Scottsbluff, NE"],
    "DDC": ["Dodge City, KS", "Garden City, KS", "Liberal, KS"],
    "DLH": ["Duluth, MN", "Superior, WI", "International Falls, MN"],
    "DMX": ["Des Moines, IA", "Ames, IA", "Fort Dodge, IA"],
    "DTX": ["Detroit, MI", "Ann Arbor, MI", "Flint, MI"],
    "DVN": ["Quad Cities, IA/IL", "Iowa City, IA", "Burlington, IA"],
    "EAX": ["Kansas City, MO", "St. Joseph, MO", "Topeka, KS"],
    "FGF": ["Grand Forks, ND", "Fargo, ND", "Thief River Falls, MN"],
    "FSD": ["Sioux Falls, SD", "Sioux City, IA", "Worthington, MN"],
    "GID": ["Hastings, NE", "Grand Island, NE", "Kearney, NE"],
    "GJT": ["Grand Junction, CO", "Montrose, CO", "Delta, CO"],
    "GLD": ["Goodland, KS", "Colby, KS", "Burlington, CO"],
    "GRB": ["Green Bay, WI", "Appleton, WI", "Wausau, WI"],
    "GRR": ["Grand Rapids, MI", "Muskegon, MI", "Kalamazoo, MI"],
    "ICT": ["Wichita, KS", "Hutchinson, KS", "Salina, KS"],
    "ILX": ["Springfield, IL", "Champaign, IL", "Decatur, IL"],
    "IND": ["Indianapolis, IN", "Lafayette, IN", "Muncie, IN"],
    "IWX": ["Fort Wayne, IN", "South Bend, IN", "Elkhart, IN"],
    "JKL": ["Jackson, KY", "Hazard, KY", "London, KY"],
    "LBF": ["North Platte, NE", "McCook, NE", "Valentine, NE"],
    "LMK": ["Louisville, KY", "Lexington, KY", "Frankfort, KY"],
    "LOT": ["Chicago, IL", "Rockford, IL", "Joliet, IL"],
    "LSX": ["St. Louis, MO", "Columbia, MO", "Belleville, IL"],
    "MKX": ["Milwaukee, WI", "Madison, WI", "Racine, WI"],
    "MPX": ["Minneapolis, MN", "St. Paul, MN", "St. Cloud, MN"],
    "MQT": ["Marquette, MI", "Escanaba, MI", "Houghton, MI"],
    "OAX": ["Omaha, NE", "Lincoln, NE", "Council Bluffs, IA"],
    "PAH": ["Paducah, KY", "Cape Girardeau, MO", "Evansville, IN"],
    "PUB": ["Pueblo, CO", "Colorado Springs, CO", "Alamosa, CO"],
    "RIW": ["Riverton, WY", "Lander, WY", "Casper, WY"],
    "SGF": ["Springfield, MO", "Joplin, MO", "Branson, MO"],
    "TOP": ["Topeka, KS", "Lawrence, KS", "Manhattan, KS"],
    "UNR": ["Rapid City, SD", "Spearfish, SD", "Pierre, SD"],
    # Eastern Region
    "AKQ": ["Wakefield, VA", "Norfolk, VA", "Richmond, VA"],
    "ALY": ["Albany, NY", "Schenectady, NY", "Saratoga Springs, NY"],
    "BGM": ["Binghamton, NY", "Ithaca, NY", "Elmira, NY"],
    "BOX": ["Boston, MA", "Worcester, MA", "Providence, RI"],
    "BTV": ["Burlington, VT", "Montpelier, VT", "Plattsburgh, NY"],
    "BUF": ["Buffalo, NY", "Rochester, NY", "Syracuse, NY"],
    "CAE": ["Columbia, SC", "Sumter, SC", "Florence, SC"],
    "CAR": ["Caribou, ME", "Presque Isle, ME", "Houlton, ME"],
    "CHS": ["Charleston, SC", "Hilton Head, SC", "Beaufort, SC"],
    "CLE": ["Cleveland, OH", "Akron, OH", "Youngstown, OH"],
    "CTP": ["State College, PA", "Harrisburg, PA", "Williamsport, PA"],
    "GSP": ["Greenville, SC", "Spartanburg, SC", "Asheville, NC"],
    "GYX": ["Gray, ME", "Portland, ME", "Lewiston, ME"],
    "ILM": ["Wilmington, NC", "Fayetteville, NC", "Jacksonville, NC"],
    "ILN": ["Wilmington, OH", "Dayton, OH", "Cincinnati, OH"],
    "LWX": ["Baltimore, MD", "Washington, DC", "Sterling, VA"],
    "MHX": ["Morehead City, NC", "New Bern, NC", "Greenville, NC"],
    "OKX": ["New York City, NY", "Long Island, NY", "Newark, NJ"],
    "PBZ": ["Pittsburgh, PA", "Morgantown, WV", "Wheeling, WV"],
    "PHI": ["Philadelphia, PA", "Trenton, NJ", "Atlantic City, NJ"],
    "RAH": ["Raleigh, NC", "Durham, NC", "Chapel Hill, NC"],
    "RLX": ["Charleston, WV", "Huntington, WV", "Beckley, WV"],
    "RNK": ["Blacksburg, VA", "Roanoke, VA", "Lynchburg, VA"],
    # Southern Region
    "ABQ": ["Albuquerque, NM", "Santa Fe, NM", "Las Cruces, NM"],
    "AMA": ["Amarillo, TX", "Lubbock, TX", "Pampa, TX"],
    "BMX": ["Birmingham, AL", "Tuscaloosa, AL", "Anniston, AL"],
    "BRO": ["Brownsville, TX", "McAllen, TX", "Harlingen, TX"],
    "CRP": ["Corpus Christi, TX", "Victoria, TX", "Laredo, TX"],
    "EPZ": ["El Paso, TX", "Las Cruces, NM", "Alamogordo, NM"],
    "EWX": ["San Antonio, TX", "Austin, TX", "New Braunfels, TX"],
    "FFC": ["Atlanta, GA", "Peachtree City, GA", "Macon, GA"],
    "FWD": ["Dallas, TX", "Fort Worth, TX", "Waco, TX"],
    "HGX": ["Houston, TX", "Galveston, TX", "College Station, TX"],
    "HUN": ["Huntsville, AL", "Decatur, AL", "Florence, AL"],
    "JAN": ["Jackson, MS", "Vicksburg, MS", "Hattiesburg, MS"],
    "JAX": ["Jacksonville, FL", "Gainesville, FL", "Daytona Beach, FL"],
    "KEY": ["Key West, FL", "Marathon, FL", "Florida Keys"],
    "LCH": ["Lake Charles, LA", "Lafayette, LA", "Beaumont, TX"],
    "LIX": ["New Orleans, LA", "Slidell, LA", "Baton Rouge, LA"],
    "LUB": ["Lubbock, TX", "Midland, TX", "Odessa, TX"],
    "LZK": ["Little Rock, AR", "Hot Springs, AR", "Pine Bluff, AR"],
    "MAF": ["Midland, TX", "Odessa, TX", "San Angelo, TX"],
    "MEG": ["Memphis, TN", "Jonesboro, AR", "Tupelo, MS"],
    "MFL": ["Miami, FL", "Fort Lauderdale, FL", "West Palm Beach, FL"],
    "MLB": ["Melbourne, FL", "Vero Beach, FL", "Cocoa Beach, FL"],
    "MOB": ["Mobile, AL", "Pensacola, FL", "Biloxi, MS"],
    "MRX": ["Morristown, TN", "Knoxville, TN", "Tri-Cities, TN/VA"],
    "OHX": ["Nashville, TN", "Clarksville, TN", "Murfreesboro, TN"],
    "OUN": ["Norman, OK", "Oklahoma City, OK", "Lawton, OK"],
    "SHV": ["Shreveport, LA", "Tyler, TX", "Texarkana, TX/AR"],
    "SJT": ["San Angelo, TX", "Abilene, TX", "Big Spring, TX"],
    "TAE": ["Tallahassee, FL", "Panama City, FL", "Dothan, AL"],
    "TBW": ["Tampa, FL", "St. Petersburg, FL", "Sarasota, FL"],
    "TSA": ["Tulsa, OK", "Muskogee, OK", "Bartlesville, OK"],
    # Western Region
    "BOI": ["Boise, ID", "Nampa, ID", "Twin Falls, ID"],
    "BYZ": ["Billings, MT", "Miles City, MT", "Sheridan, WY"],
    "EKA": ["Eureka, CA", "Arcata, CA", "Crescent City, CA"],
    "FGZ": ["Flagstaff, AZ", "Prescott, AZ", "Sedona, AZ"],
    "GGW": ["Glasgow, MT", "Wolf Point, MT", "Malta, MT"],
    "HNX": ["Hanford, CA", "Fresno, CA", "Bakersfield, CA"],
    "LKN": ["Elko, NV", "Ely, NV", "Winnemucca, NV"],
    "LOX": ["Los Angeles, CA", "Oxnard, CA", "Santa Barbara, CA"],
    "MFR": ["Medford, OR", "Klamath Falls, OR", "Ashland, OR"],
    "MSO": ["Missoula, MT", "Helena, MT", "Kalispell, MT"],
    "MTR": ["San Francisco, CA", "Monterey, CA", "San Jose, CA"],
    "OTX": ["Spokane, WA", "Coeur d'Alene, ID", "Pullman, WA"],
    "PDT": ["Pendleton, OR", "La Grande, OR", "Hermiston, OR"],
    "PIH": ["Pocatello, ID", "Idaho Falls, ID", "Rexburg, ID"],
    "PQR": ["Portland, OR", "Salem, OR", "Vancouver, WA"],
    "PSR": ["Phoenix, AZ", "Scottsdale, AZ", "Mesa, AZ"],
    "REV": ["Reno, NV", "Carson City, NV", "Lake Tahoe, CA/NV"],
    "SEW": ["Seattle, WA", "Tacoma, WA", "Olympia, WA"],
    "SGX": ["San Diego, CA", "Oceanside, CA", "Escondido, CA"],
    "SLC": ["Salt Lake City, UT", "Provo, UT", "Ogden, UT"],
    "STO": ["Sacramento, CA", "Stockton, CA", "Modesto, CA"],
    "TFX": ["Great Falls, MT", "Havre, MT", "Cut Bank, MT"],
    "TWC": ["Tucson, AZ", "Sierra Vista, AZ", "Nogales, AZ"],
    "VEF": ["Las Vegas, NV", "Henderson, NV", "Boulder City, NV"],
    # Alaska Region
    "AFC": ["Anchorage, AK", "Wasilla, AK", "Palmer, AK"],
    "AFG": ["Fairbanks, AK", "North Pole, AK", "Delta Junction, AK"],
    "AJK": ["Juneau, AK", "Ketchikan, AK", "Sitka, AK"],
    # Pacific Region
    "GUM": ["Guam", "Saipan", "Yap"],
    "HFO": ["Honolulu, HI", "Maui, HI", "Kailua-Kona, HI"],
    # Puerto Rico
    "SJU": ["San Juan, PR", "Ponce, PR", "Mayaguez, PR"],
}


class WFOProduct(BaseProduct):
    """A text product from a WFO."""

    id: str  # Unique product ID from NWS API
    wfo: str  # WFO identifier (e.g., "OUN")
    product_type: str  # Product type code (e.g., "AFD")
    expires: datetime | None = None  # For products with expiry (e.g., SPS)
    text: str | None = None  # May be None until loaded
    name: str | None = None  # Product name from API

    @property
    def title(self) -> str:
        """Human-readable title."""
        base = self.name or f"{self.product_type} from {self.wfo}"
        if self.issued:
            return f"{base} ({self.issued.strftime('%H:%M UTC')})"
        return base

    @property
    def short_title(self) -> str:
        """Short title for sidebar display."""
        if self.issued:
            return f"{self.product_type} {self.issued.strftime('%H:%M')}"
        return self.product_type

    @property
    def sidebar_id(self) -> str:
        """Unique ID for sidebar item."""
        return f"wfo-{self.wfo}-{self.id}"
