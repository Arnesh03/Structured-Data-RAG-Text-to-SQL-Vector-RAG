"""
Source text for the hospital policy corpus.

These are the documents the Vector RAG side of the system answers from. They
cover the qualitative half of a hospital's knowledge: what the rules are, how
care is delivered, what a patient is entitled to. None of it lives in the
admissions table, which is exactly why the router has two routes to choose
between.

Kept ASCII-only: FPDF's built-in Helvetica is a latin-1 font.
"""

ADMISSION_POLICY = [
    ("Purpose and Scope",
     "This policy governs how patients are admitted to the hospital, how each "
     "admission is classified, and how inpatient beds are assigned. It applies "
     "to every inpatient admission across all service lines and is reviewed "
     "annually by the Medical Executive Committee."),

    ("Admission Types",
     "Every admission is recorded as exactly one of three types. "
     "ELECTIVE: a planned admission scheduled in advance, typically for a "
     "procedure or an investigation that is not time-critical. Elective "
     "admissions require insurance pre-authorization at least 5 business days "
     "before the admission date. "
     "URGENT: the patient requires admission within 24 to 48 hours but is "
     "clinically stable. Urgent admissions may proceed before authorization is "
     "confirmed, with retroactive review within 72 hours. "
     "EMERGENCY: the patient requires immediate admission through the "
     "Emergency Department. No pre-authorization is required, and care is "
     "never delayed for financial screening."),

    ("Emergency Department Triage",
     "Patients arriving at the Emergency Department are triaged within 10 "
     "minutes of arrival using a five-level acuity scale. "
     "Level 1 (Resuscitation) is seen immediately. "
     "Level 2 (Emergent) is seen within 10 minutes. "
     "Level 3 (Urgent) is seen within 30 minutes. "
     "Level 4 (Less Urgent) is seen within 60 minutes. "
     "Level 5 (Non-Urgent) is seen within 120 minutes. "
     "Triage level is reassessed every 30 minutes for any patient still "
     "waiting. In accordance with EMTALA, every patient receives a medical "
     "screening examination regardless of insurance status or ability to pay."),

    ("Elective Admission Scheduling",
     "Elective admissions are scheduled through the Patient Access Center. "
     "The patient must complete pre-admission testing between 3 and 30 days "
     "before the admission date. Pre-admission testing includes bloodwork, an "
     "ECG for patients over 50 or with known cardiac disease, and a "
     "medication review. Elective admissions are cancelled and rescheduled if "
     "the patient has an active fever, an uncontrolled blood glucose reading "
     "above 250 mg/dL, or a blood pressure above 180/110 mmHg on the day of "
     "admission."),

    ("Room and Bed Assignment",
     "Rooms are numbered 101 through 500 and grouped into four floors. "
     "Rooms 101-200 are the medical-surgical floor. "
     "Rooms 201-300 are the step-down and telemetry floor. "
     "Rooms 301-400 are the specialty care floor, including oncology. "
     "Rooms 401-500 are the general inpatient floor. "
     "Bed assignment is driven by clinical acuity first and preference second. "
     "Private rooms are assigned by medical necessity, including infection "
     "isolation and immunosuppression; a private room requested purely for "
     "comfort carries a supplemental charge of $150 per night that most "
     "insurance plans do not cover."),

    ("Observation Status",
     "A patient may be placed in observation status rather than admitted as an "
     "inpatient when the expected stay is under 24 hours and the clinical "
     "picture is still being clarified. Observation stays are billed as "
     "outpatient care, which changes the patient's cost share. Any observation "
     "stay exceeding 48 hours must be converted to an inpatient admission or "
     "the patient must be discharged."),

    ("Transfers and Diversion",
     "Transfers to another facility occur when the required level of care is "
     "unavailable here. The accepting physician must be identified by name "
     "before transport is arranged. When inpatient capacity exceeds 95 "
     "percent, the hospital may go on diversion for incoming ambulance "
     "traffic; walk-in emergency patients are never diverted."),
]

INSURANCE_BILLING_POLICY = [
    ("Accepted Insurance Providers",
     "The hospital is in-network with five providers: Aetna, Blue Cross, "
     "Cigna, Medicare, and UnitedHealthcare. Coverage terms differ by plan, "
     "and the patient remains responsible for any deductible, copay, or "
     "coinsurance defined by their own plan. Patients insured by a provider "
     "not on this list are treated as out-of-network and receive a good-faith "
     "cost estimate before any non-emergency service."),

    ("Pre-Authorization",
     "Elective inpatient admissions, advanced imaging, and surgical procedures "
     "require pre-authorization. The Patient Access Center submits the request "
     "and most providers respond within 5 business days. Aetna, Cigna, and "
     "UnitedHealthcare require pre-authorization for all elective inpatient "
     "admissions. Medicare does not require pre-authorization for medically "
     "necessary inpatient admissions but does apply its own inpatient-only "
     "list. Care delivered without a required authorization may be denied, "
     "and the patient is not billed for a denial caused by hospital error."),

    ("Understanding Your Bill",
     "The billing amount recorded for an admission is the total charge for the "
     "episode of care. It bundles the room and board rate, nursing care, "
     "medications administered during the stay, laboratory and imaging "
     "studies, and physician services. It is a gross charge and not the "
     "patient's out-of-pocket cost: the insurer applies its contracted rate "
     "first, and the patient owes only the remaining cost share. An itemized "
     "statement is available on request at no charge and is provided within 10 "
     "business days."),

    ("Billing Timeline and Payment",
     "The first statement is mailed within 30 days of discharge. Payment is "
     "due within 30 days of the statement date. Accepted payment methods are "
     "credit card, debit card, bank transfer, check, and online payment "
     "through the patient portal. Interest-free payment plans are available "
     "for balances over $500, spread across up to 24 months. Accounts unpaid "
     "after 120 days without an active payment plan may be referred to "
     "collections, and patients receive at least three written notices before "
     "any referral."),

    ("Financial Assistance and Charity Care",
     "Financial assistance is available to patients whose household income is "
     "at or below 400 percent of the Federal Poverty Level. Patients at or "
     "below 200 percent qualify for a full write-off of the balance. Patients "
     "between 201 and 400 percent receive a sliding-scale discount from 75 "
     "percent down to 25 percent. Applications must be submitted within 240 "
     "days of the first statement, and a decision is issued within 30 days. "
     "Collections activity is suspended while an application is pending."),

    ("Billing Disputes and Corrections",
     "A patient who believes a charge is incorrect should contact Patient "
     "Financial Services within 90 days of the statement date. The disputed "
     "portion of the balance is placed on hold during review, which is "
     "completed within 30 days. Duplicate charges and charges for services not "
     "rendered are removed and the account is rebilled. Negative or credit "
     "balances are refunded to the original payment method within 21 days."),

    ("Surprise Billing Protections",
     "Under the No Surprises Act, patients receiving emergency care at this "
     "hospital are billed at in-network cost-sharing rates even when the "
     "hospital or treating clinician is out-of-network. The same protection "
     "applies to non-emergency care delivered by an out-of-network clinician "
     "at an in-network facility. Patients are never balance-billed for the "
     "difference in these situations."),
]

CLINICAL_GUIDELINES = [
    ("Scope of These Guidelines",
     "These guidelines describe the standard inpatient management of the six "
     "chronic conditions most frequently recorded at admission: arthritis, "
     "asthma, cancer, diabetes, hypertension, and obesity. They are clinical "
     "decision support, not a substitute for the attending physician's "
     "judgment for an individual patient."),

    ("Diabetes",
     "Admitted patients with diabetes have point-of-care glucose checked "
     "before each meal and at bedtime, or every 6 hours if not eating. The "
     "inpatient glycemic target is 140 to 180 mg/dL for most patients. Oral "
     "agents are generally held on admission and basal-bolus insulin is used "
     "instead. A glucose below 70 mg/dL triggers the hypoglycemia protocol "
     "immediately. Every diabetic admission includes a foot examination and a "
     "diabetes educator consult before discharge. HbA1c is drawn if none is "
     "on file within the last 90 days."),

    ("Hypertension",
     "Blood pressure is measured on admission, then at least every 8 hours. "
     "The inpatient target is below 140/90 mmHg for most patients and below "
     "130/80 mmHg for patients with diabetes or chronic kidney disease. A "
     "reading above 180/120 mmHg with signs of organ damage is a hypertensive "
     "emergency requiring intravenous therapy in a monitored bed. Home "
     "antihypertensives are continued unless the patient is hypotensive, "
     "volume depleted, or has acute kidney injury. Sodium intake is limited to "
     "2 grams per day during the stay."),

    ("Asthma",
     "Severity is assessed with peak expiratory flow and pulse oximetry on "
     "arrival and after each treatment. Target oxygen saturation is 93 to 95 "
     "percent. First-line treatment is an inhaled short-acting bronchodilator "
     "with systemic corticosteroids started within the first hour for moderate "
     "or severe exacerbations. Patients are stepped down to a metered-dose "
     "inhaler with a spacer once stable for 4 hours. No asthma patient is "
     "discharged without a written asthma action plan and confirmed inhaler "
     "technique."),

    ("Arthritis",
     "Inpatient management focuses on pain control, preserving function, and "
     "identifying inflammatory causes. Pain is scored on a 0 to 10 scale at "
     "least every 4 hours. Paracetamol is first-line for osteoarthritis pain. "
     "Ibuprofen and other NSAIDs are effective for inflammatory arthritis but "
     "are used cautiously in patients over 65 and avoided in chronic kidney "
     "disease, active peptic ulcer disease, or heart failure. Physical therapy "
     "is consulted within 24 hours of admission, and joints are mobilized "
     "early rather than rested."),

    ("Obesity",
     "Body mass index is calculated and documented on every admission. "
     "Bariatric-rated beds, chairs, and lifts are arranged in advance for "
     "patients over 350 pounds. Obesity raises the risk of venous "
     "thromboembolism, so weight-adjusted prophylaxis is standard unless "
     "contraindicated. Obstructive sleep apnea is screened for on admission "
     "because it changes sedation and analgesia planning. Nutrition and "
     "weight-management counselling is offered before discharge; participation "
     "is voluntary and never a condition of care."),

    ("Cancer",
     "Oncology admissions are managed jointly with the treating oncologist and "
     "are assigned to the specialty care floor where possible. Neutropenic "
     "fever, defined as a single temperature at or above 38.3 C with an "
     "absolute neutrophil count below 500, is a medical emergency: blood "
     "cultures are drawn and broad-spectrum antibiotics are given within 60 "
     "minutes. Pain is managed on the WHO analgesic ladder with no ceiling "
     "dose for opioids in advanced disease. Palliative care is consulted for "
     "any admission with uncontrolled symptoms or an expected prognosis under "
     "12 months, alongside active treatment rather than instead of it."),

    ("Formulary Medications",
     "Five medications account for most inpatient prescriptions in this "
     "dataset. "
     "ASPIRIN: antiplatelet and anti-inflammatory; avoided under age 16 and "
     "in active bleeding. "
     "IBUPROFEN: NSAID for inflammatory pain; caution in renal impairment, "
     "heart failure, and peptic ulcer disease. "
     "LIPITOR (atorvastatin): lipid-lowering therapy; liver enzymes checked at "
     "baseline and if symptoms of myopathy appear. "
     "PARACETAMOL (acetaminophen): first-line analgesic and antipyretic; "
     "maximum 4 grams per day for adults and 2 grams per day in liver disease. "
     "PENICILLIN: antibiotic for susceptible bacterial infection; allergy "
     "status is verified and documented before the first dose."),

    ("Interpreting Test Results",
     "Every admission carries a summary test result of Normal, Abnormal, or "
     "Inconclusive. NORMAL means findings fall within reference ranges and no "
     "further workup is indicated for the presenting problem. ABNORMAL means "
     "at least one clinically significant finding is outside reference range "
     "and requires documented follow-up. INCONCLUSIVE means the study was "
     "technically inadequate or the findings do not resolve the clinical "
     "question, and a repeat or alternative test is ordered. Abnormal and "
     "inconclusive results are communicated to the patient within 7 days and "
     "within 24 hours if the finding is critical."),
]

DISCHARGE_POLICY = [
    ("Discharge Criteria",
     "A patient is discharged when the admitting problem is resolved or stable "
     "on a regimen that can be continued at home, vital signs have been stable "
     "for at least 24 hours, pain is controlled on oral medication, the "
     "patient can tolerate oral intake and mobilize safely, and a safe "
     "destination is confirmed. The attending physician writes the discharge "
     "order; nursing completes the discharge process, typically within 4 hours "
     "of the order."),

    ("Length of Stay",
     "Expected length of stay is set on admission and reviewed daily by care "
     "management. Across the admissions in this dataset the typical stay runs "
     "from 1 to 30 days. A stay materially longer than expected triggers a "
     "care management review to identify and remove the barrier, which is most "
     "often placement, equipment, or a pending diagnostic study rather than "
     "clinical instability."),

    ("Medication Reconciliation",
     "Before discharge, a pharmacist reconciles the pre-admission medication "
     "list against the discharge list. Every change is explained to the "
     "patient in plain language, including drugs stopped, drugs started, and "
     "doses altered. The reconciled list is given to the patient in writing "
     "and sent to the primary care physician within 48 hours."),

    ("Discharge Instructions",
     "Written discharge instructions are provided in the patient's preferred "
     "language and cover the diagnosis, the medication list, activity "
     "restrictions, wound or device care, warning signs that should prompt "
     "return, and every scheduled follow-up appointment. Teach-back is used to "
     "confirm understanding: the patient explains the plan in their own words "
     "before leaving."),

    ("Follow-Up Appointments",
     "A follow-up appointment is scheduled before the patient leaves the "
     "building. Standard follow-up is within 7 days of discharge, and within "
     "48 to 72 hours for patients considered high risk for readmission. A "
     "nurse-led follow-up phone call is made within 48 hours of every "
     "discharge to confirm medications were obtained and understood."),

    ("Readmission",
     "An unplanned readmission within 30 days of discharge for a related "
     "problem is reviewed by the quality committee. Review looks for "
     "premature discharge, incomplete medication reconciliation, missing "
     "follow-up, and social barriers such as transport or housing. "
     "Readmission review is a quality improvement process and is never used to "
     "deny care or to delay a clinically indicated admission."),

    ("Leaving Against Medical Advice",
     "A patient with decision-making capacity may leave at any time. The risks "
     "of leaving are explained and documented, the patient signs the against "
     "medical advice form, and refusal to sign is itself documented. Leaving "
     "against medical advice does not void insurance coverage for care already "
     "delivered, and it never affects the patient's right to return."),
]

PATIENT_FAQ = [
    ("What are visiting hours?",
     "General inpatient visiting hours are 8:00 AM to 8:00 PM daily, with up "
     "to two visitors at the bedside at a time. Intensive care visiting is "
     "10:00 AM to 8:00 PM and is coordinated with the bedside nurse. One "
     "support person may stay overnight with a patient. Children under 12 must "
     "be accompanied by an adult who is not the patient."),

    ("How do I get a copy of my medical records?",
     "Submit a written records request to Health Information Management, in "
     "person or through the patient portal. Records are released within 30 "
     "days as required by HIPAA, and usually within 10 business days. The "
     "first electronic copy each year is free; paper copies are charged at 25 "
     "cents per page. A patient may authorize release to another person or "
     "provider in writing at any time."),

    ("Who can see my health information?",
     "Under HIPAA, protected health information is used and disclosed only for "
     "treatment, payment, and health care operations, or where the law "
     "requires it. Anyone else needs the patient's written authorization, "
     "which can be revoked at any time. Access is logged and audited, and a "
     "patient may request the access log for the past six years."),

    ("When will I get my test results?",
     "Results post to the patient portal as soon as they are finalized, "
     "typically within 24 to 72 hours for laboratory studies and within 7 days "
     "for imaging and pathology. Critical findings are communicated by phone "
     "within 24 hours of resolution rather than left to the portal. A result "
     "reported as inconclusive means the test must be repeated or a different "
     "test is needed, and the care team arranges that."),

    ("Can I choose or change my doctor?",
     "Patients may request a specific attending physician, and the request is "
     "honoured where that physician has admitting privileges and capacity. A "
     "patient may ask to change attending physicians at any point during the "
     "stay by speaking with the charge nurse or the patient advocate. The "
     "reason for a change is not required."),

    ("What should I bring to the hospital?",
     "Bring a photo identification, the insurance card, a current list of "
     "medications with doses, contact details for the primary care physician, "
     "and any advance directive or power of attorney document. Leave valuables "
     "and large amounts of cash at home; the hospital cannot be responsible "
     "for personal property kept at the bedside."),

    ("How do I raise a concern or make a complaint?",
     "Speak with the charge nurse first, since most concerns are resolved at "
     "the bedside the same day. Unresolved concerns go to the Patient Advocate "
     "office, which acknowledges every complaint within 2 business days and "
     "issues a written response within 30 days. Making a complaint never "
     "affects the care a patient receives."),

    ("What is an advance directive?",
     "An advance directive records the care a patient wants if they become "
     "unable to speak for themselves, and may name a health care proxy to "
     "decide on their behalf. The hospital asks about advance directives at "
     "every admission, provides the forms free of charge, and scans the "
     "completed document into the medical record. Having one is entirely "
     "voluntary and is never a condition of treatment."),

    ("Is interpretation available?",
     "Interpretation is provided free of charge, 24 hours a day, in more than "
     "200 languages, including American Sign Language. Family members are not "
     "used as interpreters for medical discussions or consent. Written "
     "materials are available in the patient's preferred language on request."),
]
