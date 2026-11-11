"""Starter catalogue, loaded once into an empty database.

Prices are sample figures in rupees. Edit them here before the first start,
or change them later in the lab_tests table.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LabCentre, LabTest

FAST_8 = "Fast for 8 to 10 hours before the test. Water is fine."
FAST_10 = "Fast for 10 to 12 hours before the test. Water is fine."
NO_PREP = "No special preparation needed."

# code, name, also_known_as, category, sample, fasting_hours, report_hours, price, mrp, popular, parameters, description
TESTS = [
    # Full body / basics
    ("CBC", "Complete Blood Count (CBC)", "CBC with ESR, Haemogram", "Fever & Infection", "Blood", 0, 12, 299, 450, True,
     ["Haemoglobin", "RBC count", "WBC count", "Platelet count", "Differential count", "PCV", "MCV", "MCH", "MCHC", "RDW"],
     "Checks the cells in your blood. Used to look for anaemia, infection and many other conditions."),
    ("ESR", "Erythrocyte Sedimentation Rate (ESR)", "Sed rate", "Fever & Infection", "Blood", 0, 12, 149, 250, False,
     ["ESR"], "A general marker of inflammation in the body."),
    ("CRP", "C-Reactive Protein (CRP)", "CRP quantitative", "Fever & Infection", "Blood", 0, 12, 449, 650, False,
     ["C-reactive protein"], "Rises with infection or inflammation. Often ordered with CBC during fever."),
    ("DENGUE", "Dengue NS1 Antigen", "Dengue early test", "Fever & Infection", "Blood", 0, 12, 599, 900, True,
     ["Dengue NS1 antigen"], "Detects dengue in the first days of fever."),
    ("MALARIA", "Malaria Antigen Test", "Malaria parasite (rapid)", "Fever & Infection", "Blood", 0, 8, 399, 550, False,
     ["P. falciparum antigen", "P. vivax antigen"], "Rapid test for the two common types of malaria."),
    ("TYPHOID", "Typhoid IgM (Typhidot)", "Typhidot IgM", "Fever & Infection", "Blood", 0, 12, 549, 800, False,
     ["Salmonella typhi IgM"], "Helps detect typhoid fever."),
    ("WIDAL", "Widal Test", "Typhoid slide test", "Fever & Infection", "Blood", 0, 12, 199, 300, False,
     ["S. typhi O", "S. typhi H", "S. paratyphi AH", "S. paratyphi BH"], "An older screening test for typhoid."),
    ("URINE_RE", "Urine Routine & Microscopy", "Urine R/M", "Kidney", "Urine", 0, 12, 149, 250, True,
     ["Colour", "pH", "Specific gravity", "Protein", "Glucose", "Ketones", "Pus cells", "RBC", "Casts", "Crystals"],
     "Screens for urinary infection, kidney problems and diabetes."),
    ("URINE_CS", "Urine Culture & Sensitivity", "Urine C/S", "Kidney", "Urine", 0, 72, 699, 1000, False,
     ["Organism identified", "Colony count", "Antibiotic sensitivity"],
     "Finds the bacteria causing a urine infection and which antibiotics work against it."),

    # Diabetes
    ("FBS", "Fasting Blood Sugar (FBS)", "Glucose fasting", "Diabetes", "Blood", 8, 6, 99, 150, True,
     ["Glucose, fasting"], "Measures blood sugar after an overnight fast."),
    ("PPBS", "Post Prandial Blood Sugar (PPBS)", "Glucose PP", "Diabetes", "Blood", 0, 6, 99, 150, False,
     ["Glucose, 2 hours after meal"], "Blood sugar measured 2 hours after a meal."),
    ("HBA1C", "HbA1c (Glycated Haemoglobin)", "A1c, 3-month sugar", "Diabetes", "Blood", 0, 12, 449, 700, True,
     ["HbA1c", "Estimated average glucose"], "Shows your average blood sugar over the last 2 to 3 months."),
    ("INSULIN_F", "Insulin Fasting", "Fasting insulin", "Diabetes", "Blood", 8, 24, 699, 1000, False,
     ["Insulin, fasting"], "Helps assess insulin resistance."),

    # Thyroid
    ("TSH", "TSH (Thyroid Stimulating Hormone)", "Ultrasensitive TSH", "Thyroid", "Blood", 0, 12, 249, 400, True,
     ["TSH"], "The first test for an under- or over-active thyroid."),
    ("T3T4TSH", "Thyroid Profile Total (T3, T4, TSH)", "TFT", "Thyroid", "Blood", 0, 12, 449, 700, True,
     ["Total T3", "Total T4", "TSH"], "Checks how well your thyroid gland is working."),
    ("FT3FT4TSH", "Thyroid Profile Free (FT3, FT4, TSH)", "Free thyroid panel", "Thyroid", "Blood", 0, 24, 649, 1000, False,
     ["Free T3", "Free T4", "TSH"], "A more detailed thyroid check using free hormone levels."),
    ("ANTI_TPO", "Anti-TPO Antibodies", "Thyroid peroxidase antibody", "Thyroid", "Blood", 0, 48, 899, 1300, False,
     ["Anti-TPO"], "Looks for autoimmune thyroid disease such as Hashimoto's."),

    # Heart
    ("LIPID", "Lipid Profile", "Cholesterol test", "Heart", "Blood", 10, 12, 399, 650, True,
     ["Total cholesterol", "HDL", "LDL", "VLDL", "Triglycerides", "TC/HDL ratio", "LDL/HDL ratio"],
     "Measures the fats in your blood to assess heart disease risk."),
    ("TROP_I", "Troponin I", "Cardiac troponin", "Heart", "Blood", 0, 6, 999, 1400, False,
     ["Troponin I"], "Used by doctors when heart muscle damage is suspected. Chest pain needs emergency care, not a booked test."),
    ("HSCRP", "hs-CRP (High-sensitivity CRP)", "Cardiac CRP", "Heart", "Blood", 0, 24, 599, 900, False,
     ["hs-CRP"], "A sensitive inflammation marker used in heart risk assessment."),
    ("APO", "Apolipoprotein A1 & B", "ApoA1, ApoB", "Heart", "Blood", 10, 48, 1199, 1700, False,
     ["Apolipoprotein A1", "Apolipoprotein B", "ApoB/ApoA1 ratio"], "An advanced cholesterol risk check."),

    # Liver
    ("LFT", "Liver Function Test (LFT)", "Hepatic panel", "Liver", "Blood", 8, 12, 549, 850, True,
     ["Bilirubin total", "Bilirubin direct", "SGOT (AST)", "SGPT (ALT)", "Alkaline phosphatase", "GGT",
      "Total protein", "Albumin", "Globulin", "A/G ratio"],
     "Checks how well your liver is working."),
    ("HBSAG", "Hepatitis B Surface Antigen (HBsAg)", "Hep B test", "Liver", "Blood", 0, 24, 349, 550, False,
     ["HBsAg"], "Screens for hepatitis B infection."),
    ("HCV", "Hepatitis C Antibody (Anti-HCV)", "Hep C test", "Liver", "Blood", 0, 24, 649, 950, False,
     ["Anti-HCV"], "Screens for hepatitis C infection."),

    # Kidney
    ("KFT", "Kidney Function Test (KFT)", "Renal function test, RFT", "Kidney", "Blood", 0, 12, 549, 850, True,
     ["Urea", "Creatinine", "Uric acid", "BUN", "Sodium", "Potassium", "Chloride", "Calcium", "Phosphorus"],
     "Checks how well your kidneys filter waste."),
    ("CREAT", "Serum Creatinine", "Creatinine", "Kidney", "Blood", 0, 12, 149, 250, False,
     ["Creatinine", "eGFR"], "A quick check of kidney function."),
    ("URIC", "Uric Acid", "Serum urate", "Kidney", "Blood", 0, 12, 149, 250, False,
     ["Uric acid"], "High levels can cause gout and kidney stones."),
    ("ELECTRO", "Electrolytes (Na, K, Cl)", "Serum electrolytes", "Kidney", "Blood", 0, 12, 349, 550, False,
     ["Sodium", "Potassium", "Chloride"], "Checks the salt balance in your blood."),

    # Vitamins & minerals
    ("VITD", "Vitamin D (25-OH)", "Vit D3", "Vitamins", "Blood", 0, 24, 799, 1400, True,
     ["25-Hydroxy vitamin D"], "Low vitamin D is very common and affects bones and immunity."),
    ("VITB12", "Vitamin B12", "Cobalamin", "Vitamins", "Blood", 0, 24, 599, 1000, True,
     ["Vitamin B12"], "Low B12 can cause tiredness, numbness and anaemia."),
    ("IRON", "Iron Studies", "Iron profile", "Vitamins", "Blood", 8, 24, 699, 1100, False,
     ["Serum iron", "TIBC", "Transferrin saturation", "UIBC"], "Checks for iron deficiency or overload."),
    ("FERRITIN", "Ferritin", "Iron stores", "Vitamins", "Blood", 0, 24, 499, 800, False,
     ["Ferritin"], "Shows how much iron your body has stored."),
    ("CALCIUM", "Calcium", "Serum calcium", "Vitamins", "Blood", 0, 12, 149, 250, False,
     ["Calcium"], "Important for bones, nerves and muscles."),
    ("FOLATE", "Folic Acid", "Vitamin B9", "Vitamins", "Blood", 0, 24, 699, 1000, False,
     ["Folate"], "Low folate can cause anaemia. Important in pregnancy."),

    # Women's health & hormones
    ("BHCG", "Beta HCG (Pregnancy Test)", "Blood pregnancy test", "Women's Health", "Blood", 0, 12, 499, 750, False,
     ["Beta HCG"], "Confirms pregnancy and tracks early pregnancy."),
    ("PCOD", "PCOD Hormone Panel", "PCOS panel", "Women's Health", "Blood", 0, 48, 1499, 2400, True,
     ["LH", "FSH", "Prolactin", "Testosterone", "DHEA-S", "TSH"], "Hormones commonly checked when PCOD/PCOS is suspected."),
    ("AMH", "AMH (Anti-Mullerian Hormone)", "Ovarian reserve test", "Women's Health", "Blood", 0, 48, 1299, 2000, False,
     ["AMH"], "Gives an idea of ovarian reserve. Often used in fertility planning."),
    ("PROLACTIN", "Prolactin", "PRL", "Hormones", "Blood", 0, 24, 449, 700, False,
     ["Prolactin"], "Checks for hormone imbalances that affect periods and fertility."),
    ("TESTO", "Testosterone Total", "Serum testosterone", "Hormones", "Blood", 0, 24, 599, 900, False,
     ["Testosterone, total"], "Measures the main male hormone. Also used in women's hormone checks."),
    ("CORTISOL", "Cortisol (Morning)", "Serum cortisol AM", "Hormones", "Blood", 0, 24, 549, 850, False,
     ["Cortisol"], "The stress hormone. Best collected between 7 and 9 am."),
    ("PSA", "PSA Total (Prostate)", "Prostate specific antigen", "Hormones", "Blood", 0, 24, 699, 1100, False,
     ["PSA, total"], "Screens for prostate problems in men over 50."),

    # Allergy & others
    ("IGE", "Total IgE", "Allergy screen", "Allergy", "Blood", 0, 24, 549, 850, False,
     ["Total IgE"], "Raised in many allergic conditions."),
    ("ALLERGY_FOOD", "Food Allergy Panel (20 allergens)", "Food IgE panel", "Allergy", "Blood", 0, 96, 2999, 4500, False,
     ["Milk", "Egg", "Wheat", "Peanut", "Soy", "Fish", "Prawn", "Rice", "Chickpea", "Others (11 more)"],
     "Checks for IgE allergy to 20 common foods."),
    ("COVID_RTPCR", "COVID-19 RT-PCR", "Coronavirus PCR", "Fever & Infection", "Swab", 0, 24, 499, 800, False,
     ["SARS-CoV-2 RNA"], "Nasal and throat swab test for COVID-19."),
    ("BLOOD_GROUP", "Blood Group & Rh Type", "ABO grouping", "Fever & Infection", "Blood", 0, 6, 99, 150, False,
     ["ABO group", "Rh factor"], "Finds your blood group."),
]

# code, name, category, fasting_hours, report_hours, price, mrp, popular, included test codes, description
PACKAGES = [
    ("PKG_FULLBODY_ESS", "Full Body Checkup Essential", "Full Body Checkup", 10, 24, 1299, 2800, True,
     ["CBC", "FBS", "LIPID", "LFT", "KFT", "T3T4TSH", "URINE_RE"],
     "A good yearly check of blood, sugar, cholesterol, liver, kidney and thyroid."),
    ("PKG_FULLBODY_ADV", "Full Body Checkup Advanced", "Full Body Checkup", 10, 48, 2499, 5200, True,
     ["CBC", "ESR", "FBS", "HBA1C", "LIPID", "LFT", "KFT", "T3T4TSH", "VITD", "VITB12", "IRON", "URINE_RE"],
     "Everything in Essential plus vitamins, iron and 3-month sugar."),
    ("PKG_DIABETES", "Diabetes Care Package", "Diabetes", 10, 24, 899, 1700, True,
     ["FBS", "PPBS", "HBA1C", "LIPID", "CREAT", "URINE_RE"],
     "For people with diabetes or at risk: sugar control, cholesterol and kidney check."),
    ("PKG_HEART", "Heart Health Package", "Heart", 10, 48, 1799, 3200, True,
     ["LIPID", "HSCRP", "APO", "FBS", "CBC", "ELECTRO"], "Cholesterol, inflammation and other heart risk markers."),
    ("PKG_THYROID", "Thyroid Care Package", "Thyroid", 0, 48, 1199, 2100, False,
     ["FT3FT4TSH", "ANTI_TPO", "CBC"], "A full thyroid work-up including autoimmune antibodies."),
    ("PKG_FEVER", "Fever Panel", "Fever & Infection", 0, 24, 1399, 2400, True,
     ["CBC", "CRP", "DENGUE", "MALARIA", "TYPHOID", "URINE_RE"], "The usual tests for fever lasting more than 2 to 3 days."),
    ("PKG_WOMEN", "Women's Wellness Package", "Women's Health", 10, 48, 1999, 3900, True,
     ["CBC", "T3T4TSH", "VITD", "VITB12", "IRON", "CALCIUM", "FBS", "LIPID"],
     "Thyroid, anaemia, vitamins and bone health for women."),
    ("PKG_VITAMIN", "Vitamin Deficiency Package", "Vitamins", 0, 24, 1199, 2500, False,
     ["VITD", "VITB12", "FOLATE", "IRON", "CALCIUM"], "Checks the most common vitamin and mineral deficiencies."),
    ("PKG_SENIOR", "Senior Citizen Package (60+)", "Full Body Checkup", 10, 48, 2999, 6000, False,
     ["CBC", "FBS", "HBA1C", "LIPID", "LFT", "KFT", "T3T4TSH", "VITD", "VITB12", "PSA", "URINE_RE", "ELECTRO"],
     "A thorough yearly check for people over 60."),
]

CENTRES = [
    ("VaidyaSaathi Diagnostics - Central", "12 Main Road, near City Hospital", "Your City", "560001", "080 4000 1001"),
    ("VaidyaSaathi Diagnostics - North", "45 Ring Road, opposite Metro Station", "Your City", "560024", "080 4000 1002"),
    ("VaidyaSaathi Diagnostics - South", "8 Lake View Complex, 2nd Floor", "Your City", "560068", "080 4000 1003"),
]


def seed(db: Session) -> None:
    if db.scalar(select(LabTest.id).limit(1)) is None:
        by_code = {}
        for code, name, aka, cat, sample, fast, rep, price, mrp, pop, params, desc in TESTS:
            prep = FAST_10 if fast >= 10 else FAST_8 if fast else NO_PREP
            t = LabTest(code=code, name=name, also_known_as=aka, category=cat, sample_type=sample,
                        fasting_hours=fast, report_hours=rep, price=price, mrp=mrp, is_popular=pop,
                        parameters=params, description=desc, preparation=prep)
            db.add(t)
            by_code[code] = t
        for code, name, cat, fast, rep, price, mrp, pop, inc, desc in PACKAGES:
            params = []
            for c in inc:
                params.extend(by_code[c].parameters)
            samples = sorted({by_code[c].sample_type for c in inc})
            db.add(LabTest(code=code, name=name, also_known_as=f"{len(inc)} tests, {len(params)} parameters",
                           category=cat, sample_type=" + ".join(samples), fasting_hours=fast, report_hours=rep,
                           price=price, mrp=mrp, is_popular=pop, parameters=[by_code[c].name for c in inc],
                           description=desc, preparation=FAST_10 if fast else NO_PREP,
                           is_package=True, included_codes=inc))
    if db.scalar(select(LabCentre.id).limit(1)) is None:
        for name, addr, city, pin, phone in CENTRES:
            db.add(LabCentre(name=name, address=addr, city=city, pincode=pin, phone=phone))
    db.commit()
