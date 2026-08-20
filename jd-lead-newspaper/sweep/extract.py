#!/usr/bin/env python3
"""
ACTION-004: Newspaper Lead Extraction (Measurement Phase)

Segments newspaper full-text OCR pages into candidate classified ads,
filters out matrimonial/property/non-recruitment ads, extracts fields,
applies email-first company name resolution, applies hard drop gates,
scores against Jobdrive ICP, and produces a measurement report.

Zero writes to production leads or leads_park databases.
"""

import os
import re
import sys
import json
import sqlite3
import argparse
import datetime

PHONE_RE = re.compile(r'(?:\+?91[\s\-]?)?[6-9]\d{9}')
EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

FREE_PROVIDERS = {
    'gmail.com', 'yahoo.com', 'yahoo.co.in', 'hotmail.com', 'rediffmail.com',
    'outlook.com', 'live.com', 'aol.com', 'icloud.com', 'mail.com', 'zoho.com',
    'ymail.com', 'protonmail.com', 'proton.me', 'msn.com'
}

GENERIC_LOCALPARTS = {
    'hr', 'hrd', 'cv', 'career', 'careers', 'jobs', 'info', 'admin', 'contact',
    'sales', 'apply', 'resume', 'resumes', 'job', 'hiring', 'recruitment', 'recruit',
    'office', 'desk', 'helpdesk', 'inquiry', 'enquiry', 'work', 'staff', 'team',
    'interview', 'interviews', 'vacancy', 'vacancies', 'account', 'accounts', 'personnel',
    'support', 'billing', 'finance', 'head', 'headoffice', 'recruitments', 'admn',
    'letters', 'editor', 'reporter', 'feedback', 'editorial', 'response', 'classified', 'classifieds'
}

PERSONAL_NAMES = {
    'dhairesh', 'neeraj', 'santosh', 'santoshmagic', 'rkumar', 'pawan', 'rahul',
    'melraj', 'arunbhai', 'tahir', 'krishna', 'srushti', 'anirban', 'amit', 'pooja',
    'priya', 'vikas', 'sanjay', 'deepak', 'manoj', 'rajesh', 'ramesh', 'suresh',
    'rohit', 'ajay', 'vijay', 'anil', 'sunil', 'alok', 'ashok', 'ravi', 'rakesh',
    'dinesh', 'mukesh', 'kamal', 'naresh', 'vinod', 'pramod', 'manish', 'ashish',
    'bose', 'sharma', 'singh', 'gupta', 'agarwal', 'verma', 'mishra',
    'kumar', 'pandey', 'yadav', 'jain', 'patel', 'shah', 'mehta', 'desai', 'joshi'
}

BUSINESS_KEYWORDS = [
    'international', 'technologies', 'technology', 'enterprises', 'enterprise',
    'engineering', 'healthcare', 'consulting', 'consultants', 'consultancy',
    'logistics', 'solutions', 'properties', 'property', 'industries', 'industry',
    'packaging', 'chemicals', 'chemical', 'security', 'services', 'service',
    'infotech', 'reality', 'systems', 'system', 'trading', 'traders', 'trader',
    'tradex', 'swastik', 'united', 'pharma', 'motors', 'motor', 'global',
    'exports', 'export', 'imports', 'import', 'energy', 'metals', 'metal',
    'steels', 'steel', 'papers', 'paper', 'prints', 'print', 'textile',
    'textiles', 'plastic', 'plastics', 'foods', 'food', 'infra', 'lube',
    'tech', 'auto', 'chem', 'sanskar', 'sanat', 'aryus', 'trimax',
    'gradient', 'rail', 'rawji', 'chandok', 'hitech', 'super', 'sonics',
    'sonic', 'legal', 'oil', 'group', 'india', 'ind', 'care', 'corp',
    'labs', 'lab', 'agro', 'power', 'wood', 'glass', 'stone', 'home',
    'homes', 'pack', 'build', 'builders', 'plus', 'star', 'smart',
    'prime', 'apex', 'ltd', 'pvt', 'llp', 'inc', 'co', 'media', 'learning',
    'realityllp', 'realityllpac', 'classic', 'lubetech', 'supersonics',
    'gradientsecurity', 'railind', 'trimaxunited', 'sanskartradex',
    'sanatswastikoil', 'hitechcon', 'rbpcareer', 'tdsjmk', 'sanakhanlegal',
    'shreeommrealityllpac'
]
BUSINESS_KEYWORDS_SORTED = sorted(BUSINESS_KEYWORDS, key=len, reverse=True)

LOCALITY_BLOCKLIST = {
    'delhi', 'new delhi', 'mumbai', 'ahmedabad', 'noida', 'greater noida',
    'gurgaon', 'gurugram', 'ghaziabad', 'faridabad', 'okhla', 'dwarka',
    'rohini', 'saket', 'lajpat nagar', 'pitampura', 'janakpuri', 'laxmi nagar',
    'nehru place', 'patel nagar', 'rajouri garden', 'south ex', 'connaught place',
    'connaught circus', 'chandni chowk', 'shahdara', 'karkardooma', 'nsp',
    'netaji subhash place', 'dilshad garden', 'mayur vihar', 'paschim vihar',
    'vikaspuri', 'kalkaji', 'tughlakabad', 'jasola', 'mohan estate', 'sahibabad',
    'kundli', 'manesar', 'dharuhera', 'bawal', 'neemrana', 'bhiwadi', 'baddi',
    'ankleshwar', 'vapi', 'bharuch', 'halol', 'vadodara', 'surat', 'rajkot',
    'gandhinagar', 'pune', 'pimpri', 'chinchwad', 'hinjewadi', 'hadapsar',
    'sanaswadi', 'chakan', 'talegaon', 'bhosari', 'taloja', 'rabale', 'mahape',
    'turbhe', 'kopar khairane', 'belapur', 'seawoods', 'nerul', 'juinagar',
    'ghansoli', 'digha', 'dombivli', 'kalyan', 'ambernath', 'badlapur',
    'bhiwandi', 'vasai', 'virar', 'mira road', 'bhayandar', 'dahisar',
    'borivali', 'kandivali', 'malad', 'goregaon', 'jogeshwari', 'andheri',
    'andheri east', 'andheri west', 'vile parle', 'santacruz', 'khar', 'bandra',
    'mahim', 'matunga', 'dadar', 'parel', 'lower parel', 'prabhadevi', 'mahalaxmi',
    'mumbai central', 'grant road', 'charni road', 'marine lines', 'churchgate',
    'cst', 'vt', 'byculla', 'mazgaon', 'wadala', 'sion', 'kurla', 'ghatkopar',
    'vikhroli', 'kanjurmarg', 'bhandup', 'mulund', 'thane', 'airoli', 'vashi',
    'sanpada', 'cbd belapur', 'kharghar', 'mansarovar', 'khandeshwar',
    'panvel', 'nariman point', 'fort', 'colaba', 'chembur', 'worli', 'karol bagh',
    'ashok vihar', 'pearl business park', 'marol naka', 'marol', 'beadonpura'
}

KNOWN_LOCATIONS = [
    # Multi-word names first
    'Navi Mumbai', 'Greater Noida', 'New Delhi', 'South Delhi', 'North Delhi', 'West Delhi', 'East Delhi', 'Central Delhi',
    'South Extn', 'South Ex', 'Connaught Place', 'Connaught Circus', 'Nehru Place', 'Netaji Subhash Place', 'Laxmi Nagar',
    'Lajpat Nagar', 'Patel Nagar', 'Rajouri Garden', 'Chandni Chowk', 'Dilshad Garden', 'Mayur Vihar', 'Paschim Vihar',
    'Ashok Vihar', 'Shalimar Bagh', 'Uttam Nagar', 'Karol Bagh', 'Nizamuddin East', 'Nizamuddin', 'Pearl Business Park',
    'Marol Naka', 'Nariman Point', 'Lower Parel', 'Marine Lines', 'Grant Road', 'Charni Road', 'Mumbai Central',
    'Mira Road', 'CBD Belapur', 'Kopar Khairane', 'Andheri East', 'Andheri West', 'Vile Parle',
    'Chhatrapati Sambhajinagar', 'Sri Ganganagar',
    # Single word NCR / Localities
    'Noida', 'Gurgaon', 'Gurugram', 'Ghaziabad', 'Faridabad', 'Bahadurgarh', 'Kundli', 'Manesar', 'Dharuhera',
    'Bawal', 'Neemrana', 'Bhiwadi', 'Sonipat', 'Panipat', 'Karnal', 'Rohtak', 'Hisar', 'Ambala', 'Rewari', 'Yamunanagar',
    'Dwarka', 'Rohini', 'Saket', 'Pitampura', 'Janakpuri', 'Okhla', 'Kalkaji', 'Tughlakabad', 'Jasola', 'Shahdara',
    'Karkardooma', 'Vikaspuri', 'Delhi',
    # Single word Mumbai MMR
    'Mumbai', 'Thane', 'Kalyan', 'Dombivli', 'Bhiwandi', 'Vasai', 'Virar', 'Bhayandar', 'Panvel', 'Kharghar', 'Vashi',
    'Belapur', 'Nerul', 'Airoli', 'Mahape', 'Rabale', 'Taloja', 'Ambernath', 'Badlapur', 'Digha', 'Ghansoli', 'Juinagar',
    'Sanpada', 'Seawoods', 'Mansarovar', 'Khandeshwar', 'Uran',
    'Andheri', 'Bandra', 'Borivali', 'Dadar', 'Worli', 'Chembur', 'Kurla', 'Goregaon', 'Malad', 'Kandivali', 'Dahisar',
    'Santacruz', 'Ghatkopar', 'Mulund', 'Bhandup', 'Powai', 'Vikhroli', 'Kanjurmarg', 'Parel', 'Prabhadevi', 'Mahalaxmi',
    'Colaba', 'Fort', 'Byculla', 'Wadala', 'Sion', 'Churchgate', 'Mazgaon', 'Marol',
    # Maharashtra
    'Pune', 'Pimpri', 'Chinchwad', 'Hinjewadi', 'Hadapsar', 'Chakan', 'Talegaon', 'Bhosari', 'Sanaswadi', 'Nagpur',
    'Nashik', 'Aurangabad', 'Solapur', 'Kolhapur', 'Amravati', 'Nanded', 'Jalgaon', 'Akola', 'Latur', 'Dhule',
    'Ahmednagar', 'Satara', 'Sangli', 'Ratnagiri',
    # Gujarat
    'Ahmedabad', 'Surat', 'Vadodara', 'Rajkot', 'Gandhinagar', 'Ankleshwar', 'Vapi', 'Bharuch', 'Halol', 'Bhavnagar',
    'Jamnagar', 'Junagadh', 'Morbi', 'Mehsana', 'Valsad', 'Navsari',
    # Rajasthan
    'Jaipur', 'Jodhpur', 'Udaipur', 'Kota', 'Ajmer', 'Bhilwara', 'Alwar', 'Bikaner', 'Sikar', 'Pali', 'Bharatpur',
    # Punjab & Haryana
    'Chandigarh', 'Mohali', 'Panchkula', 'Ludhiana', 'Amritsar', 'Jalandhar', 'Patiala', 'Bathinda', 'Hoshiarpur',
    # North / Hills
    'Shimla', 'Solan', 'Baddi', 'Dharamsala', 'Dehradun', 'Haridwar', 'Rishikesh', 'Roorkee', 'Haldwani', 'Rudrapur',
    'Jammu', 'Srinagar',
    # UP
    'Lucknow', 'Kanpur', 'Agra', 'Varanasi', 'Prayagraj', 'Allahabad', 'Meerut', 'Aligarh', 'Bareilly', 'Moradabad',
    'Saharanpur', 'Gorakhpur', 'Jhansi', 'Mathura', 'Muzaffarnagar', 'Ayodhya',
    # MP
    'Indore', 'Bhopal', 'Gwalior', 'Jabalpur', 'Ujjain',
    # South
    'Bangalore', 'Bengaluru', 'Hyderabad', 'Secunderabad', 'Chennai', 'Coimbatore', 'Madurai', 'Trichy', 'Salem',
    'Kochi', 'Cochin', 'Trivandrum', 'Thiruvananthapuram', 'Kozhikode', 'Calicut', 'Thrissur', 'Visakhapatnam',
    'Vizag', 'Vijayawada', 'Guntur', 'Tirupati', 'Mysore', 'Mysuru', 'Mangalore', 'Mangaluru', 'Hubli', 'Belgaum',
    # East
    'Kolkata', 'Howrah', 'Patna', 'Ranchi', 'Jamshedpur', 'Dhanbad', 'Bokaro', 'Bhubaneswar', 'Cuttack', 'Rourkela',
    'Raipur', 'Bhilai', 'Bilaspur', 'Guwahati', 'Shillong'
]

CANONICAL_LOCATION_MAP = {
    'gurugram': 'Gurgaon',
    'bengaluru': 'Bangalore',
    'prayagraj': 'Allahabad',
    'cochin': 'Kochi',
    'trivandrum': 'Thiruvananthapuram',
    'calicut': 'Kozhikode',
    'vizag': 'Visakhapatnam',
    'mysuru': 'Mysore',
    'mangaluru': 'Mangalore',
    'belagavi': 'Belgaum',
    'chhatrapati sambhajinagar': 'Aurangabad',
    'south extn': 'South Ex',
}

KNOWN_LOCATIONS_SORTED = sorted(KNOWN_LOCATIONS, key=len, reverse=True)
LOCATION_PATTERNS = [(re.compile(r'\b' + re.escape(loc) + r'\b', re.IGNORECASE), loc) for loc in KNOWN_LOCATIONS_SORTED]


def extract_location(text: str) -> str | None:
    """Extract recognized Indian city/locality from ad text."""
    for pat, canonical in LOCATION_PATTERNS:
        if pat.search(text):
            low = canonical.lower()
            return CANONICAL_LOCATION_MAP.get(low, canonical)
    return None


ROLE_BLOCKLIST = {
    'engineer', 'diploma', 'accountant', 'account', 'accounts', 'senior accountant',
    'junior accountant', 'manager', 'executive', 'sales', 'marketing', 'telecaller',
    'receptionist', 'driver', 'operator', 'technician', 'helper', 'security', 'guard',
    'clerk', 'peon', 'cook', 'waiter', 'steno', 'stenographer', 'typist', 'data entry',
    'back office', 'office assistant', 'field officer', 'project manager', 'civil engineer',
    'mechanical engineer', 'electrical engineer', 'quality chemist', 'chemist',
    'plant manager', 'store keeper', 'purchaser', 'commercial manager', 'computer operator',
    'graphic designer', 'cashier', 'billing executive', 'merchandiser', 'teacher',
    'faculty', 'professor', 'lecturer', 'principal', 'doctor', 'nurse', 'dentist',
    'advocate', 'ca', 'inter ca', 'article clerk', 'fresher', 'freshers', 'trainee',
    'intern', 'interns', 'graduate', 'post graduate', 'b.com', 'm.com', 'b.sc', 'm.sc',
    'b.tech', 'm.tech', 'bca', 'mca', 'mba', 'bba', 'llb', 'llm', '10th pass', '12th pass',
    'experience', 'qualification', 'salary', 'handsome salary', 'urgent', 'urgently',
    'full time', 'part time', 'male', 'female', 'candidates', 'walk in', 'interview',
    'walkin', 'vacancy', 'vacancies', 'situations vacant', 'job vacancy', 'hiring',
    'required', 'wanted', 'req', 'reqd', 'requires', 'marketing manager exp', 'retail showroom'
}

MATRIMONIAL_MARKERS = [
    r'\bsm4\b', r'\bpqm\b', r'\balliance\b', r'\bbride\b', r'\bgroom\b',
    r'\bmatrimonial\b', r'\bmanglik\b', r'\bmglk\b', r'\bteetotaler\b',
    r'\bbiodata\b', r'\bgotra\b', r'\bhoroscope\b', r'\bkundli\b',
    r'\bcaste\b', r'\bbrahmin\b', r'\brajput\b', r'\bkhatri\b', r'\bagarwal\b',
    r'\bjat\b', r'\bdivorcee\b', r'\bnever married\b', r'\bwheatish\b',
    r'\bhomely\b', r'\bseeks\b.*?\b(?:girl|boy|bride|groom)\b',
    r'\b\d\s*[\'’]\s*\d{1,2}\s*(?:\"|\'\'|in|inches)?\b',
    r'\bmatch for\b', r'\balliance invited\b', r'\blooking for.*?\b(?:girl|boy)\b',
    r'\bstatus family\b', r'\baffluent family\b', r'\bgujarati boy\b', r'\bgujarati girl\b',
    r'\bshwetamber\b', r'\bjain\b', r'\bvaish\b', r'\bkayastha\b', r'\bsunni\b', r'\bshia\b'
]
MATRIMONIAL_PATS = [re.compile(p, re.IGNORECASE) for p in MATRIMONIAL_MARKERS]

PROPERTY_MARKERS = [
    r'\bbhk\b', r'\bsq\s*ft\b', r'\bsqft\b', r'\bplot\b', r'\bflat\b',
    r'\bkothi\b', r'\bbuilder floor\b', r'\bfor sale\b', r'\bfor rent\b',
    r'\blease\b', r'\bfreehold\b', r'\bpossession\b', r'\bcommercial space\b',
    r'\bpagdi\b', r'\bcarpet area\b', r'\boffice space\b', r'\bproperty\b'
]
PROPERTY_PATS = [re.compile(p, re.IGNORECASE) for p in PROPERTY_MARKERS]

RECRUITMENT_MARKERS = [
    r'\bvacancy\b', r'\bvacancies\b', r'\bvacant\b', r'\bwalk-in\b', r'\bwalkin\b',
    r'\bresume\b', r'\bcv\b', r'\bapply\b', r'\brecruitment\b',
    r'\bappointment\b', r'\bappointments\b', r'\brequired\b', r'\bwanted\b',
    r'\bhiring\b', r'\bpost of\b', r'\binterview\b', r'\bexperience\b',
    r'\bqualification\b', r'\bsituations vacant\b', r'\bjob opening\b', r'\burgently required\b'
]
RECRUITMENT_PATS = [re.compile(p, re.IGNORECASE) for p in RECRUITMENT_MARKERS]

GOV_MARKERS = [
    r'\bu\.?p\.?s\.?c\b', r'\bs\.?s\.?c\b', r'\bp\.?s\.?c\b', r'\bgovt\b', r'\bgovernment\b',
    r'\bministry of\b', r'\bdepartment of\b', r'\bnigam\b', r'\bmunicipal\b', r'\bmunicipality\b',
    r'\bcorporation of\b', r'\brailway\b', r'\bpolice\b', r'\bcrpf\b', r'\bbsf\b', r'\bcourt\b',
    r'\bcollectorate\b', r'\bpublic sector\b', r'\bpsu\b', r'\bpwd\b', r'\bsebi\b', r'\bnhai\b',
    r'\bisro\b', r'\bdrdo\b', r'\bicmr\b', r'\baiims\b', r'\biit\b', r'\biim\b', r'\bnit\b',
    r'\bcisf\b', r'\bstate transmission\b', r'\bport authority\b', r'\bkvic\b', r'\burban development mission\b',
    r'\bcentral silk board\b', r'\bunion public service\b', r'\bdefence\b', r'\bcsir\b'
]
GOV_PATS = [re.compile(p, re.IGNORECASE) for p in GOV_MARKERS]

EDU_MARKERS = [
    r'\bcoaching\b', r'\btuition\b', r'\biit-jee\b', r'\bneet\b',
    r'\btutorials\b', r'\bentrance exam\b', r'\bcoaching centre\b', r'\bcoaching center\b'
]
EDU_PATS = [re.compile(p, re.IGNORECASE) for p in EDU_MARKERS]

HIRING_VERB_MARKERS = [
    r'\brequired(?!\s+to\b)\b', r'\brequires\b', r'\bwanted\b', r'\bvacancy\b',
    r'\bvacancies\b', r'\bvacant\b', r'\bwalk-in\b', r'\bwalkin\b', r'\brecruitment\b',
    r'\bappointment\b', r'\bresume\b', r'\bcv\b', r'\bapply\b', r'\bhiring\b',
    r'\bpost of\b', r'\binterview\b', r'\bcandidates\b', r'\bapplications invited\b',
    r'\bsend biodata\b', r'आवश्यकता', r'चाहिए', r'भर्ती', r'रिक्ति'
]
HIRING_VERB_PATS = [re.compile(p, re.IGNORECASE) for p in HIRING_VERB_MARKERS]

STAFFING_MARKERS = [
    r'\bconsultancy\b', r'\bconsultancies\b', r'\bmanpower\b', r'\bplacement\b',
    r'\bstaffing\b', r'\bhr services\b', r'\brecruitment agency\b', r'\bjob placement\b'
]
STAFFING_PATS = [re.compile(p, re.IGNORECASE) for p in STAFFING_MARKERS]

NEWS_MARKERS = [
    r'\bepaper\b', r'\btimes news network\b', r'\bhindustan times\b', r'\btimes of india\b',
    r'\bcorrespondent\b', r'\bpress trust of india\b',
    r'\bpti\b', r'\bposted missing\b', r'\bmissing female\b', r'\bmissing male\b',
    r'\bkidnapped\b', r'\bmurder\b', r'\bassault\b', r'\bpolice station\b',
    r'\btender notice\b', r'\bauction notice\b', r'\brated r\b'
]
NEWS_PATS = [re.compile(p, re.IGNORECASE) for p in NEWS_MARKERS]

ICP_MARKERS = [
    r'\bpharma\b', r'\bpharmaceutical\b', r'\bchemical\b', r'\bchemicals\b',
    r'\bnutra\b', r'\bnutraceutical\b', r'\bfood\b', r'\bmanufacturing\b',
    r'\bproduction\b', r'\bpackaging\b', r'\bindustrial\b', r'\bplastic\b',
    r'\bengineering\b', r'\bformulation\b', r'\bapi\b', r'\bcosmetic\b',
    r'\blaboratory\b', r'\bquality chemist\b', r'\bauto industries\b', r'\btransformer\b',
    r'\bfoundry\b', r'\bsteel\b', r'\bmetal\b', r'\btextile\b', r'\bgarment\b',
    r'\bschool\b', r'\bcollege\b', r'\bvidyalaya\b', r'\bconvent\b',
    r'\bcbse\b', r'\bicse\b', r'\buniversity\b', r'\bhospital\b',
    r'\bnursing\b', r'\bclinic\b', r'\bdiagnostic\b', r'\bpathology\b'
]
ICP_PATS = [re.compile(p, re.IGNORECASE) for p in ICP_MARKERS]

HIGH_VOL_ROLES = [
    r'\bsales\b', r'\bmarketing\b', r'\btelecaller\b', r'\btele-caller\b',
    r'\baccountant\b', r'\baccounts\b', r'\bdriver\b', r'\boperator\b',
    r'\btechnician\b', r'\bhelper\b', r'\bsecurity\b', r'\bguard\b',
    r'\bexecutive\b', r'\bback office\b', r'\breceptionist\b', r'\bfield officer\b',
    r'\bclerk\b', r'\bpeon\b', r'\bstore keeper\b', r'\belectrician\b', r'\bwelder\b'
]
HIGH_VOL_PATS = [re.compile(p, re.IGNORECASE) for p in HIGH_VOL_ROLES]

ROLE_PATTERNS = [
    # Multi-word & Specific Titles First
    (re.compile(r'\bVice\s+Principals?\b', re.I), "Vice Principal"),
    (re.compile(r'\bPrincipals?\b', re.I), "Principal"),
    (re.compile(r'\b(?:Special\s+Educator|Sp\.?\s*Educator|Spl\.?\s*Edu(?:cator)?)\b', re.I), "Special Educator"),
    (re.compile(r'\b(?:Librarians?|Lib)\b', re.I), "Librarian"),
    (re.compile(r'\bLab(?:oratory)?\s+Assistants?\b', re.I), "Lab Assistant"),
    (re.compile(r'\bLab(?:oratory)?\s+Attendants?\b', re.I), "Lab Attendant"),
    (re.compile(r'\bLab(?:oratory)?\s+Technicians?\b', re.I), "Lab Technician"),
    (re.compile(r'\bSports?\s+Coach(?:es)?\b', re.I), "Sports Coach"),
    (re.compile(r'\b(?:Child\s+)?Counsell?ors?\b', re.I), "Counsellor"),
    (re.compile(r'\bWardens?\b', re.I), "Warden"),
    (re.compile(r'\bLecturers?\b', re.I), "Lecturer"),
    (re.compile(r'\bProfessors?\b', re.I), "Professor"),
    (re.compile(r'\bFacult(?:y|ies)\b', re.I), "Faculty"),
    (re.compile(r'\b(?:PGT|Post\s+Graduate\s+Teacher)(?:\s+[A-Za-z]+)?\b', re.I), "PGT"),
    (re.compile(r'\b(?:TGT|Trained\s+Graduate\s+Teacher)(?:\s+[A-Za-z]+)?\b', re.I), "TGT"),
    (re.compile(r'\b(?:PRT|Primary\s+Teachers?)\b', re.I), "PRT"),
    (re.compile(r'\b(?:NTT|Nursery\s+Teacher\s+Training|Nursery\s+Teachers?)\b', re.I), "NTT"),
    (re.compile(r'\bPET(?:\s*\(?[MFmf]\)?)?\b|\bPhysical\s+Education\s+Teachers?\b', re.I), "PET"),
    (re.compile(r'\bTeachers?\b|\bTeaching\s+Positions?\b|\bexp\.?\s*trs\b|\btrs\b', re.I), "Teacher"),
    (re.compile(r'\bSanskrit\b', re.I), "Sanskrit"),
    (re.compile(r'\bHistory\b', re.I), "History"),

    # Medical
    (re.compile(r'\bStaff\s+Nurses?\b', re.I), "Staff Nurse"),
    (re.compile(r'\bNurses?\b', re.I), "Nurse"),
    (re.compile(r'\bGNM\b', re.I), "GNM"),
    (re.compile(r'\bB\.?Sc(?:\.?|\s+)\s*Nursing\b', re.I), "B.Sc Nursing"),
    (re.compile(r'\bANM\b', re.I), "ANM"),
    (re.compile(r'\bResident\s+Medical\s+Officers?\b|\bRMO\b', re.I), "Resident Medical Officer"),
    (re.compile(r'\bMBBS\b', re.I), "MBBS"),
    (re.compile(r'\bBAMS\b', re.I), "BAMS"),
    (re.compile(r'\bBDS\b', re.I), "BDS"),
    (re.compile(r'\bBHMS\b', re.I), "BHMS"),
    (re.compile(r'\bDoctors?\b', re.I), "Doctor"),
    (re.compile(r'\bDentists?\b', re.I), "Dentist"),
    (re.compile(r'\bPhysicians?\b', re.I), "Physician"),
    (re.compile(r'\b(?:Paediatricians?|Pediatricians?)\b', re.I), "Paediatrician"),
    (re.compile(r'\bOphthalmologists?\b', re.I), "Ophthalmologist"),
    (re.compile(r'\bCardiologists?\b', re.I), "Cardiologist"),
    (re.compile(r'\bUrologists?\b', re.I), "Urologist"),
    (re.compile(r'\b(?:Gynaecologists?|Gynecologists?)\b', re.I), "Gynecologist"),
    (re.compile(r'\bDermatologists?\b', re.I), "Dermatologist"),
    (re.compile(r'\b(?:Orthopaedics?|Orthopedics?|Orthopaedists?|Orthopedists?)\b', re.I), "Orthopedic"),
    (re.compile(r'\bNeurologists?\b', re.I), "Neurologist"),
    (re.compile(r'\bOncologists?\b', re.I), "Oncologist"),
    (re.compile(r'\bRadiologists?\b', re.I), "Radiologist"),
    (re.compile(r'\bPathologists?\b', re.I), "Pathologist"),
    (re.compile(r'\b(?:Anesthesiologists?|Anaesthesiologists?|Anaesthetists?|Anesthetists?)\b', re.I), "Anesthesiologist"),
    (re.compile(r'\bSurgeons?\b', re.I), "Surgeon"),
    (re.compile(r'\bPsychiatrists?\b', re.I), "Psychiatrist"),
    (re.compile(r'\bNephrologists?\b', re.I), "Nephrologist"),
    (re.compile(r'\bGastroenterologists?\b', re.I), "Gastroenterologist"),
    (re.compile(r'\bPulmonologists?\b', re.I), "Pulmonologist"),
    (re.compile(r'\bENT\s+Specialists?\b', re.I), "ENT Specialist"),
    (re.compile(r'\bPharmacists?\b', re.I), "Pharmacist"),
    (re.compile(r'\bRadiographers?\b', re.I), "Radiographer"),
    (re.compile(r'\bPhysiotherapists?\b', re.I), "Physiotherapist"),
    (re.compile(r'\bWard\s+Boys?\b', re.I), "Ward Boy"),
    (re.compile(r'\bOT\s+Technicians?\b', re.I), "OT Technician"),

    # Commercial and Admin
    (re.compile(r'\b(?:Senior|Sr\.?)\s+Accountants?\b', re.I), "Senior Accountant"),
    (re.compile(r'\b(?:Junior|Jr\.?)\s+Accountants?\b', re.I), "Junior Accountant"),
    (re.compile(r'\bAccounts?\s+Assistants?\b', re.I), "Accounts Assistant"),
    (re.compile(r'\bAccounts?\s+Executives?\b', re.I), "Account Executive"),
    (re.compile(r'\bAccountants?\b|\bAccounts\b|\bExprienced\.?\s*Acc\b', re.I), "Accountant"),
    (re.compile(r'\bAudit\s+Assistants?\b', re.I), "Audit Assistant"),
    (re.compile(r'\bAudit\s+Executives?\b', re.I), "Audit Executive"),
    (re.compile(r'\bTally\s+Operators?\b', re.I), "Tally Operator"),
    (re.compile(r'\bComputer\s+Operators?\b', re.I), "Computer Operator"),
    (re.compile(r'\bData\s+Entry(?:\s+Operators?)?\b', re.I), "Data Entry Operator"),
    (re.compile(r'\bReceptionists?\b', re.I), "Receptionist"),
    (re.compile(r'\bOffice\s+Assistants?\b|\bOffice\s+Asst\.?\b', re.I), "Office Assistant"),
    (re.compile(r'\bClerks?\b', re.I), "Clerk"),
    (re.compile(r'\bAdmin(?:\.|\s+Executives?)?\b', re.I), "Admin Executive"),
    (re.compile(r'\bStore\s*Keepers?\b', re.I), "Store Keeper"),
    (re.compile(r'\bPurchase\s+Executives?\b', re.I), "Purchase Executive"),
    (re.compile(r'\bPurchasers?\b', re.I), "Purchaser"),
    (re.compile(r'\bCashiers?\b', re.I), "Cashier"),
    (re.compile(r'\bTele-?callers?\b|\bTele-?calling(?:\s+Executives?)?\b', re.I), "Telecaller"),
    (re.compile(r'\bBack\s+Office(?:\s+Executives?)?\b', re.I), "Back Office"),
    (re.compile(r'\bGraphic\s+Designers?\b', re.I), "Graphic Designer"),
    (re.compile(r'\bSoftware\s+(?:Developers?|Engineers?)\b|\bWeb\s+Developers?\b', re.I), "Software Developer"),
    (re.compile(r'\bBilling\s+Executives?\b', re.I), "Billing Executive"),
    (re.compile(r'\bCommercial\s+Managers?\b', re.I), "Commercial Manager"),
    (re.compile(r'\bHR\s+Managers?\b', re.I), "HR Manager"),
    (re.compile(r'\bHR\s+Executives?\b|\bHR\b', re.I), "HR Executive"),

    # Sales and Field
    (re.compile(r'\bSales\s+Managers?\b', re.I), "Sales Manager"),
    (re.compile(r'\bSales\s+Executives?\b', re.I), "Sales Executive"),
    (re.compile(r'\bMarketing\s+Managers?\b', re.I), "Marketing Manager"),
    (re.compile(r'\bMarketing\s+Executives?\b', re.I), "Marketing Executive"),
    (re.compile(r'\bField\s+Officers?\b', re.I), "Field Officer"),
    (re.compile(r'\bBusiness\s+Development\s+Executives?\b|\bBDE\b', re.I), "Business Development Executive"),
    (re.compile(r'\bArea\s+Managers?\b', re.I), "Area Manager"),
    (re.compile(r'\bCounter\s+Sales(?:\s+Executives?)?\b', re.I), "Counter Sales"),

    # Technical and Industrial
    (re.compile(r'\bSite\s+Supervisors?\b', re.I), "Site Supervisor"),
    (re.compile(r'\bSite\s+Engineers?\b', re.I), "Site Engineer"),
    (re.compile(r'\bCivil\s+Engineers?\b', re.I), "Civil Engineer"),
    (re.compile(r'\bElectrical\s+Engineers?\b', re.I), "Electrical Engineer"),
    (re.compile(r'\bMechanical\s+Engineers?\b', re.I), "Mechanical Engineer"),
    (re.compile(r'\bEstimation\s+Engineers?\b', re.I), "Estimation Engineer"),
    (re.compile(r'\bBOQ\s+Engineers?\b', re.I), "BOQ Engineer"),
    (re.compile(r'\bInterior\s+Designers?\b', re.I), "Interior Designer"),
    (re.compile(r'\bDraughts(?:man|men)\b|\bDrafts(?:man|men)\b', re.I), "Draughtsman"),
    (re.compile(r'\bFitters?\b', re.I), "Fitter"),
    (re.compile(r'\bWelders?\b', re.I), "Welder"),
    (re.compile(r'\bElectricians?\b', re.I), "Electrician"),
    (re.compile(r'\bMachine\s+Operators?\b', re.I), "Machine Operator"),
    (re.compile(r'\bCNC\s+Operators?\b', re.I), "CNC Operator"),
    (re.compile(r'\bQuality\s+Chemists?\b', re.I), "Quality Chemist"),
    (re.compile(r'\bChemists?\b', re.I), "Chemist"),
    (re.compile(r'\bProduction\s+Supervisors?\b', re.I), "Production Supervisor"),
    (re.compile(r'\bProduction\s+Managers?\b', re.I), "Production Manager"),
    (re.compile(r'\bPlant\s+Managers?\b', re.I), "Plant Manager"),
    (re.compile(r'\bProject\s+Managers?\b', re.I), "Project Manager"),
    (re.compile(r'\bMaintenance\s+Engineers?\b', re.I), "Maintenance Engineer"),
    (re.compile(r'\bTechnicians?\b', re.I), "Technician"),
    (re.compile(r'\bHelpers?\b', re.I), "Helper"),

    # Service
    (re.compile(r'\bSecurity\s+Guards?\b', re.I), "Security Guard"),
    (re.compile(r'\bGuards?\b', re.I), "Guard"),
    (re.compile(r'\bDrivers?\b', re.I), "Driver"),
    (re.compile(r'\bPeons?\b', re.I), "Peon"),
    (re.compile(r'\bCooks?\b|\bChefs?\b', re.I), "Cook"),
    (re.compile(r'\bHousekeeping(?:\s+Staff)?\b', re.I), "Housekeeping"),
    (re.compile(r'\bAttendants?\b', re.I), "Attendant"),
    (re.compile(r'\bDelivery\s+Boys?\b', re.I), "Delivery Boy"),
]

STOPWORDS = {
    'for', 'to', 'at', 'in', 'on', 'the', 'and', 'with', 'from', 'of', 'or',
    'a', 'an', 'is', 'are', 'req', 'reqd', 'wanted', 'required', 'urgent',
    'urgently', 'immediate', 'immediately', 'apply', 'send', 'contact', 'email',
    'call', 'male', 'female', 'experienced', 'fresher', 'freshers', 'candidate',
    'candidates', 'exp', 'salary', 'handsome salary', 'qualification', 'walk in',
    'walkin', 'interview', 'vacancy', 'vacancies', 'situations vacant', 'job vacancy',
    'hiring', 'requires', 'gender', 'age', 'full time', 'part time', 'phone',
    'mobile', 'whatsapp', 'resume', 'biodata', 'cv', 'post', 'posts', 'staff', 'need', 'needs'
}


def classify_candidate(text: str) -> tuple[str, int, int, int]:
    m_cnt = sum(len(p.findall(text)) for p in MATRIMONIAL_PATS)
    p_cnt = sum(len(p.findall(text)) for p in PROPERTY_PATS)
    r_cnt = sum(len(p.findall(text)) for p in RECRUITMENT_PATS)

    if m_cnt > 0 and m_cnt >= r_cnt and m_cnt >= p_cnt:
        return 'matrimonial', m_cnt, p_cnt, r_cnt
    if p_cnt > 0 and p_cnt >= r_cnt and p_cnt > m_cnt:
        return 'property', m_cnt, p_cnt, r_cnt
    if r_cnt > 0:
        return 'recruitment', m_cnt, p_cnt, r_cnt
    return 'other', m_cnt, p_cnt, r_cnt


TRIGGER_RE = re.compile(
    r'\b(?:REQUIRE|REQUIRES|REQUIRED|WANTED|REQ\.?|REQD|VACANCY|VACANCIES|SITUATION\s+VACANT|SITUATIONS\s+VACANT|HIRING|JOB\s+VACANCY|WALK-IN|WALKIN|APPOINTMENT|APPOINTMENTS|APPLICATIONS\s+INVITED|URGENTLY\s+REQUIRED|CAREER\s+OPPORTUNITY)\b',
    re.IGNORECASE
)

CATEGORY_HEADER_RE = re.compile(
    r'(?:\n\s*[-=_]{3,}|\b(?:OTHER\s+VACANCIES|MULTIPLE\s+VACANCIES|GENERAL\s+MULTIPLE\s+VACANCIES|CLASSIFIEDS?|APPOINTMENTS?|SITUATIONS?\s+VACANT|MEDICAL|ACCOUNTS?|SALES|MARKETING|TEACHERS?|PROFESSIONALS?|SECURITY|DOMESTIC|HOTEL|PLACEMENT|ENGINEERING)\b)',
    re.IGNORECASE
)


def extract_clean_ad_text(text: str, anchor_s: int, anchor_e: int, prev_anchor_e: int = 0, next_anchor_s: int | None = None, window: int = 800) -> str:
    between_text = text[prev_anchor_e:anchor_s]
    sec_matches = list(CATEGORY_HEADER_RE.finditer(between_text))
    trig_matches = list(TRIGGER_RE.finditer(between_text))

    if sec_matches:
        start_pos = prev_anchor_e + sec_matches[-1].end()
    elif trig_matches and (anchor_s - (prev_anchor_e + trig_matches[-1].start())) >= 25:
        start_pos = prev_anchor_e + trig_matches[-1].start()
    elif prev_anchor_e > 0 and (anchor_s - prev_anchor_e) <= window:
        start_pos = prev_anchor_e
    else:
        left_limit = max(0, anchor_s - window)
        snippet = text[left_limit:anchor_s]
        sec_splits = list(CATEGORY_HEADER_RE.finditer(snippet))
        if sec_splits:
            start_pos = left_limit + sec_splits[-1].end()
        else:
            trig_splits = list(TRIGGER_RE.finditer(snippet))
            if trig_splits:
                valid = [m for m in trig_splits if (anchor_s - (left_limit + m.start())) >= 25]
                start_pos = left_limit + valid[-1].start() if valid else left_limit
            else:
                start_pos = left_limit

    right_limit = min(len(text), next_anchor_s if next_anchor_s is not None else len(text), anchor_e + 150)
    snippet_after = text[anchor_e:right_limit]
    end_sec = list(CATEGORY_HEADER_RE.finditer(snippet_after))
    end_trig = list(TRIGGER_RE.finditer(snippet_after))
    end_pos = right_limit
    if end_sec:
        end_pos = min(end_pos, anchor_e + end_sec[0].start())
    if end_trig:
        end_pos = min(end_pos, anchor_e + end_trig[0].start())

    return text[start_pos:end_pos].strip()


def extract_roles(text: str) -> list[str]:
    clean_text = EMAIL_RE.sub(' ', text)
    clean_text = PHONE_RE.sub(' ', clean_text)

    delims = r'[,/\n;&|•+]'
    raw_fragments = [f.strip() for f in re.split(delims, clean_text) if f.strip()]
    found = []

    for raw_frag in raw_fragments:
        frag = raw_frag
        for pat, role in ROLE_PATTERNS:
            m = pat.search(frag)
            if m:
                if role not in found:
                    found.append(role)
                frag = frag[:m.start()] + ' ' * (m.end() - m.start()) + frag[m.end():]

    if not found:
        t = clean_text
        for pat, role in ROLE_PATTERNS:
            m = pat.search(t)
            if m:
                if role not in found:
                    found.append(role)
                t = t[:m.start()] + ' ' * (m.end() - m.start()) + t[m.end():]

    if not found:
        m = re.search(
            r'(?:wanted|required|requires|post\s+of)\s+(?!(?:for|at|in|on|by|to|with|from|urgently|immediate|a|an|the)\b)([A-Za-z\s]{3,30}?)(?:\n|,|\.|\bfor\b|\bwith\b|\bsalary\b|\bexp\b|\bcontact\b|\bcall\b|\bapply\b|\bat\b|\bin\b)',
            clean_text,
            re.IGNORECASE
        )
        if m:
            cand = m.group(1).strip()
            cand_clean = re.sub(r'[^A-Za-z\s]', '', cand).strip()
            words = [w.lower() for w in cand_clean.split() if w]
            filtered_words = [w for w in words if w not in STOPWORDS]
            if filtered_words and len(' '.join(filtered_words)) >= 3:
                cand_title = ' '.join(filtered_words).title()
                if cand_title.lower() not in STOPWORDS:
                    found.append(cand_title)

    return found


def split_domain_or_local(s: str) -> str:
    s_clean = re.sub(r'[\d_\-\.]+', ' ', s).strip()
    s_camel = re.sub(r'([a-z])([A-Z])', r'\1 \2', s_clean)
    if ' ' in s_camel:
        words = [w.capitalize() for w in s_camel.split() if w]
        return " ".join(words)

    curr = s.lower()
    sub_words = []
    while curr:
        matched = False
        for w in BUSINESS_KEYWORDS_SORTED:
            if curr.startswith(w):
                title_w = w.title()
                if w == 'llp': title_w = 'LLP'
                elif w == 'pvt': title_w = 'Pvt'
                elif w == 'ltd': title_w = 'Ltd'
                elif w == 'ind': title_w = 'Ind'
                elif w == 'hitech': title_w = 'Hitech'
                elif w == 'con': title_w = 'Construction'
                elif w == 'shreeommrealityllpac': title_w = 'Shree Omm Reality LLP'
                elif w == 'lubetech': title_w = 'Lube Tech'
                elif w == 'supersonics': title_w = 'Supersonics'
                elif w == 'sanskartradex': title_w = 'Sanskar Tradex'
                elif w == 'sanatswastikoil': title_w = 'Sanat Swastik Oil'
                elif w == 'trimaxunited': title_w = 'Trimax United'
                elif w == 'gradientsecurity': title_w = 'Gradient Security'
                elif w == 'railind': title_w = 'Rail Ind'
                elif w == 'sanakhanlegal': title_w = 'Sana Khan Legal'
                sub_words.append(title_w)
                curr = curr[len(w):]
                matched = True
                break
        if not matched:
            if not sub_words:
                sub_words.append(curr.title())
                curr = ""
            else:
                sub_words.append(curr.title())
                curr = ""
    return " ".join(sub_words)


def resolve_company_name(text: str, email: str | None) -> tuple[str | None, str]:
    # 1. Business email domain
    if email:
        email_clean = email.strip().lower()
        if '@' in email_clean:
            local, domain = email_clean.split('@', 1)
            if domain not in FREE_PROVIDERS:
                core_domain = re.sub(r'\.(?:co\.in|net\.in|org\.in|ac\.in|gov\.in|res\.in|com|in|org|net|co|io|biz|info)$', '', domain)
                if len(core_domain) >= 3 and core_domain not in ['mail', 'email', 'contact', 'web']:
                    return split_domain_or_local(core_domain), "business_email_domain"

    # 2. Free-provider local part (non-generic, non-personal)
    # Note: GENERIC_LOCALPARTS matches whole string rather than substring,
    # so compound handles like 'rbpcareer' slip through without explicit substring matching.
    if email:
        email_clean = email.strip().lower()
        if '@' in email_clean:
            local, domain = email_clean.split('@', 1)
            if domain in FREE_PROVIDERS:
                local_base = re.sub(r'[\d_\-\.]+$', '', local)
                if local_base and local_base not in GENERIC_LOCALPARTS and len(local_base) >= 4:
                    if local_base not in PERSONAL_NAMES:
                        has_biz = any(bw in local_base for bw in ['trade', 'tradex', 'oil', 'tech', 'reality', 'legal', 'con', 'group', 'auto', 'security', 'career', 'llp', 'pharma', 'solutions', 'systems', 'infra', 'foods', 'industries', 'enterprises', 'chem', 'steel', 'metal', 'pack', 'paper', 'lube', 'sonics', 'united'])
                        if has_biz:
                            return split_domain_or_local(local_base), "free_email_localpart"

    # 3. Layout heuristic (last resort with blocklists)
    clean_text = PHONE_RE.sub('', text)
    clean_text = EMAIL_RE.sub('', clean_text)

    comp_pat = re.search(r'([A-Z][A-Za-z0-9\s&\'\.\-]{2,40}\s+(?:Pvt\.?\s*Ltd\.?|Private\s*Limited|Ltd\.?|Limited|LLP|Inc\.?|Industries|Enterprise[s]?|Corporation|Group|Hospital|Clinic|Pharma|Chemicals|Infotech|Solutions|Foundation|Reality|Systems|Products|Foods|Security|Bank\s+Ltd))', clean_text)
    if comp_pat:
        cand = comp_pat.group(1).strip()
        cand_lower = cand.lower()
        if not any(loc in cand_lower for loc in LOCALITY_BLOCKLIST if len(loc) > 4) and not any(r in cand_lower for r in ['hospital', 'clinic', 'nursing']):
            words = cand.split()
            while words and words[0].lower() in ['wanted', 'required', 'req', 'reqd', 'hiring', 'for', 'at', 'in', 'and', 'the', 'urgently']:
                words.pop(0)
            if words:
                return " ".join(words), "layout_formal_entity"

    at_pat = re.search(r'\b(?:at|for)\s+([A-Z][A-Za-z0-9\.\'\s]{2,30}?)(?:,|\.|\n|\bMumbai\b|\bDelhi\b|\bAhmedabad\b|\bContact\b|\bCall\b|\bEmail\b|\bSend\b|\bWA\b)', clean_text)
    if at_pat:
        cand = at_pat.group(1).strip()
        cand_lower = cand.lower()
        if cand_lower not in LOCALITY_BLOCKLIST and cand_lower not in ROLE_BLOCKLIST:
            words = cand.split()
            while words and words[0].lower() in ['wanted', 'required', 'req', 'reqd', 'hiring', 'for', 'at', 'in', 'and', 'the', 'urgently']:
                words.pop(0)
            if len(words) >= 1 and len(" ".join(words)) >= 3:
                return " ".join(words).title(), "layout_at_for"

    pkg_pat = re.search(r'([A-Z][A-Za-z\s]{2,25}\s+Co\.)', clean_text)
    if pkg_pat:
        cand = pkg_pat.group(1).strip()
        if cand.lower() not in ROLE_BLOCKLIST:
            return cand, "layout_co"

    # 4. Fallback: null / no_company
    return None, "no_company"


def normalize_company_key(company_name: str | None) -> str | None:
    if not company_name:
        return None
    k = company_name.lower()
    k = re.sub(r'\b(pvt|private|ltd|limited|llp|inc|co|company|industries|india)\b', '', k, flags=re.I)
    k = re.sub(r'[^a-z0-9]', '', k)
    return f"np_{k}" if k else None


def score_lead(ad_text: str, roles: list[str], phone: str | None, email: str | None, is_icp: bool) -> tuple[int, str]:
    score = 0
    if re.search(r'\b(?:10\s*-\s*100|20\s*-\s*50|50\s*-\s*100)\s*employees?\b', ad_text, re.IGNORECASE):
        score += 25
    else:
        score += 15

    if is_icp:
        score += 20

    if any(p.search(ad_text) for p in HIGH_VOL_PATS) or any(r in ["Sales Executive", "Accountant", "Driver", "Telecaller", "Security Guard", "Store Keeper"] for r in roles):
        score += 15

    if len(roles) >= 2 or re.search(r'\b(?:multiple\s+vacancies|positions)\b', ad_text, re.IGNORECASE):
        score += 15

    if phone or email:
        score += 10

    score += 10  # No ATS

    if email:
        domain = email.split('@')[-1].lower()
        if domain not in FREE_PROVIDERS:
            score += 20

    tier = "hot" if score >= 70 else ("warm" if score >= 50 else "drop")
    return score, tier


def main():
    parser = argparse.ArgumentParser(description="Newspaper Lead Extractor (Measurement Phase)")
    parser.add_argument("--db", type=str, default="/root/newspaper_sweep/sweep.db", help="Path to SQLite database")
    parser.add_argument("--output", type=str, default="/root/newspaper_sweep/extract_report.json", help="Path to output JSON")
    parser.add_argument("--drop-no-role", action="store_true", default=False, help="Hard drop leads with no resolvable job role (default: False)")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database not found at {args.db}", file=sys.stderr)
        sys.exit(1)

    with sqlite3.connect(args.db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT edition_key, paper, city, edition_date, weekday, page_no, full_text
            FROM page_scan
            WHERE full_text IS NOT NULL
            ORDER BY edition_date DESC, page_no ASC
            """
        )
        rows = cursor.fetchall()

    print(f"Loaded {len(rows)} pages with full_text from {args.db}")

    classification_counts = {"matrimonial": 0, "property": 0, "recruitment": 0, "other": 0}
    drop_counts = {
        "enterprise": 0,
        "government": 0,
        "no_contact": 0,
        "size_gate": 0,
        "coaching_centre": 0,
        "advertisement_not_vacancy": 0,
        "dupe": 0,
        "no_role": 0,
        "low_score": 0,
        "other": 0
    }

    survivors = []
    seen_contacts = set()
    total_candidates = 0
    toi_delhi_aug2_p14_stats = {"total_candidates": 0, "matrimonial": 0, "property": 0, "recruitment": 0, "other": 0, "survivors": 0}

    for r in rows:
        ed_key, paper, page_city, ed_date, wd, pno, text = r
        is_p14_target = (ed_key == "toi-delhi" and ed_date == "2026-08-02" and pno == 14)

        anchors = []
        for m in PHONE_RE.finditer(text):
            anchors.append((m.start(), m.end(), 'phone', m.group(0)))
        for m in EMAIL_RE.finditer(text):
            if 'timesofindia' not in m.group(0).lower() and 'hindustantimes' not in m.group(0).lower():
                anchors.append((m.start(), m.end(), 'email', m.group(0)))
        anchors.sort()

        clusters = []
        for a in anchors:
            if not clusters:
                clusters.append([a])
            else:
                prev_end = clusters[-1][-1][1]
                if a[0] - prev_end <= 120:
                    clusters[-1].append(a)
                else:
                    clusters.append([a])

        for i, cl in enumerate(clusters):
            total_candidates += 1
            min_s = min(a[0] for a in cl)
            max_e = max(a[1] for a in cl)

            prev_e = clusters[i-1][-1][1] if i > 0 else 0
            next_s = clusters[i+1][0][0] if i < len(clusters)-1 else len(text)

            ad_text = extract_clean_ad_text(text, min_s, max_e, prev_e, next_s)
            cat, m_cnt, p_cnt, r_cnt = classify_candidate(ad_text)
            classification_counts[cat] += 1

            if is_p14_target:
                toi_delhi_aug2_p14_stats["total_candidates"] += 1
                toi_delhi_aug2_p14_stats[cat] += 1

            if cat != "recruitment":
                continue

            phones = [a[3] for a in cl if a[2] == 'phone']
            emails = [a[3] for a in cl if a[2] == 'email']

            phone = phones[0] if phones else None
            email = emails[0] if emails else None

            if not phone and not email:
                drop_counts["no_contact"] += 1
                continue

            if not any(p.search(ad_text) for p in HIRING_VERB_PATS):
                drop_counts["advertisement_not_vacancy"] += 1
                continue

            if any(p.search(ad_text) for p in NEWS_PATS) and not any(p.search(ad_text) for p in STAFFING_PATS):
                drop_counts["other"] += 1
                continue

            if any(p.search(ad_text) for p in GOV_PATS):
                drop_counts["government"] += 1
                continue

            if any(p.search(ad_text) for p in EDU_PATS):
                drop_counts["coaching_centre"] += 1
                continue

            if any(p.search(ad_text) for p in STAFFING_PATS) or re.search(r'\b(?:1000\+|5000\+|fortune\s*500)\b', ad_text, re.IGNORECASE):
                drop_counts["enterprise"] += 1
                continue

            contact_key = phone if phone else email
            if contact_key in seen_contacts:
                drop_counts["dupe"] += 1
                continue
            seen_contacts.add(contact_key)

            roles = extract_roles(ad_text)
            if not roles:
                drop_counts["no_role"] += 1
                if args.drop_no_role:
                    continue

            comp_name, source = resolve_company_name(ad_text, email)
            is_icp = bool(any(p.search(ad_text) for p in ICP_PATS))

            score, tier = score_lead(ad_text, roles, phone, email, is_icp)

            if tier == "drop":
                drop_counts["low_score"] += 1
                continue

            if is_p14_target:
                toi_delhi_aug2_p14_stats["survivors"] += 1

            comp_key = normalize_company_key(comp_name)

            survivors.append({
                "edition_key": ed_key,
                "paper": paper,
                "city": page_city,
                "edition_date": ed_date,
                "weekday": wd,
                "page_no": pno,
                "company_name": comp_name,
                "company_key": comp_key,
                "company_source": source,
                "contact_phone": phone,
                "contact_email": email,
                "role_titles": roles,
                "score": score,
                "tier": tier,
                "is_icp": is_icp,
                "raw_ad_text": ad_text
            })

    hot_count = sum(1 for s in survivors if s["tier"] == "hot")
    warm_count = sum(1 for s in survivors if s["tier"] == "warm")
    icp_count = sum(1 for s in survivors if s["is_icp"])
    non_icp_count = len(survivors) - icp_count

    report_data = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_pages_scanned": len(rows),
        "total_candidates": total_candidates,
        "classification_breakdown": classification_counts,
        "recruitment_drop_reasons": drop_counts,
        "survivors_summary": {
            "total_survivors": len(survivors),
            "hot": hot_count,
            "warm": warm_count,
            "icp_qualified": icp_count,
            "non_icp": non_icp_count
        },
        "acceptance_check_toi_delhi_2026_08_02_p14": toi_delhi_aug2_p14_stats,
        "sample_survivors_20": survivors[:20]
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print("\n==================================================")
    print("NEWSPAPER LEAD EXTRACTION EVALUATION REPORT")
    print("==================================================")
    print(f"Total Pages Analyzed: {len(rows)}")
    print(f"Total Candidate Ads Found: {total_candidates}")
    print("\nCandidate Classification Breakdown:")
    for cat, cnt in classification_counts.items():
        pct = (cnt / total_candidates * 100) if total_candidates else 0
        print(f"  - {cat.capitalize():15s}: {cnt:4d} ({pct:5.1f}%)")

    print("\nRecruitment Drop-Reason Tally:")
    for reason, cnt in drop_counts.items():
        print(f"  - {reason:27s}: {cnt:4d}")

    print("\nLead Survivor Yield:")
    print(f"  - Hot Leads (70+ pts) : {hot_count:4d}")
    print(f"  - Warm Leads (50-69)  : {warm_count:4d}")
    print(f"  - Total Survivors     : {len(survivors):4d}")

    print("\nJobdrive ICP Breakdown among Survivors:")
    print(f"  - Target ICP (Pharma / Chemical / Nutra / Food / Mfg) : {icp_count:4d} ({(icp_count/len(survivors)*100 if survivors else 0):.1f}%)")
    print(f"  - Non-ICP (Services / Retail / Real Estate / Other)   : {non_icp_count:4d} ({(non_icp_count/len(survivors)*100 if survivors else 0):.1f}%)")

    print("\nAcceptance Test Check (TOI Delhi 2026-08-02 Page 14):")
    print(f"  - Total Candidate Ads  : {toi_delhi_aug2_p14_stats['total_candidates']}")
    print(f"  - Matrimonial Classified: {toi_delhi_aug2_p14_stats['matrimonial']}")
    print(f"  - Non-Matrimonial      : {toi_delhi_aug2_p14_stats['property'] + toi_delhi_aug2_p14_stats['recruitment'] + toi_delhi_aug2_p14_stats['other']}")
    print(f"  - Leaked Survivors     : {toi_delhi_aug2_p14_stats['survivors']} (PASS = 0)")

    print("\n==================================================")
    print("20 SAMPLE SURVIVORS (COMPANY, KEY, PHONE, EMAIL, ROLES, SCORE)")
    print("==================================================")
    for idx, s in enumerate(survivors[:20], 1):
        roles_str = " | ".join(s['role_titles'])
        comp_disp = s['company_name'] if s['company_name'] else "(null - no_company)"
        key_disp = s['company_key'] if s['company_key'] else "None"
        print(f"{idx:02d}. [{s['tier'].upper()} {s['score']}pts] {comp_disp} [key: {key_disp}] ({s['company_source']})")
        print(f"    Phone: {s['contact_phone']} | Email: {s['contact_email']}")
        print(f"    Roles: {roles_str}")
        print(f"    ICP: {'YES' if s['is_icp'] else 'NO'} | Edition: {s['edition_key']} {s['edition_date']} p{s['page_no']}")
        print()


if __name__ == "__main__":
    main()
