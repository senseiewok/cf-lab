# Cystic Fibrosis Project Ideas

Project ideas for the Sensei Ewok Research Lab focused on Cystic Fibrosis (CF) research and patient support. **Load `cf-research-context` before acting on any of these** — it holds the disease grounding, the lab's claim boundaries, and the PHI rules.

## Scope triage (added 2026-10-04)

Read against `cf-research-context` ("what this lab may and may not claim") and the no-PHI rule, several ideas below cannot be built by this lab as written. They are kept for the record, with the conflict named, so nobody re-derives them.

| Idea | Conflict | Salvageable form |
| --- | --- | --- |
| Medication Tracker, Nutrition Planner (enzyme dosing), Emergency Response Guide | Dosing, first-aid steps, and reminders about a person's medicines are clinical guidance | None for this lab. Link to care-team and CFF resources instead |
| Symptom Journal, Longitudinal Study Tracker, Patient-Reported Outcomes Platform, Multi-center Data Consortium | Each collects or links individual-level health data; "anonymized" or "privacy-preserving" does not exempt small CF cohorts | Synthetic-fixture demonstrations of a schema, clearly labelled, with no real-data pathway |
| Drug Response Predictor | Interprets genotype to predict an individual's treatment response, which is explicitly out of scope | None. CFTR2 already covers variant-level annotation; link to it |
| Clinical Trial Simulator, Outcome Dashboard (real-time, multi-center) | Require patient-level data or imply clinical monitoring | Dashboard of *published aggregate* registry indicators with per-value provenance; see `research/sources/catalog.yaml` and the cf-registry-extract scoping memo (a private session document, not in the repo) |
| Insurance & Billing Assistant, Financial Aid Navigator | Not clinical, but jurisdiction-specific, fast-changing, and consequential if wrong; needs a maintenance commitment the lab has not made | Curated link list with access dates, no eligibility logic |
| Literature Review Assistant, Research Data Registry, Protocol Repository, CF Data Standards, Open Lab Notebook | Within scope | Proceed, subject to primary-source grounding and the evidence-ledger rules in `security-browsing` section 9 |

This is a triage, not a verdict on usefulness. Several excluded ideas would help people; they belong with organisations that have clinical governance, and the right contribution from this lab is to point at them, not build them.

The ideas are organized into three categories:

## 1. For CF Patients and Families

These projects focus on practical tools and resources that directly help patients, families, and caregivers manage CF daily.

### Patient Management Tools

- **Medication Tracker**: Mobile/web app to track inhalers, pills, enzymes, and IV medications with reminders and dosage calendars
- **Symptom Journal**: Interactive journal for tracking daily symptoms, energy levels, and triggers with visualization and trend analysis
- **Hospital Visit Prep**: Checklist generator for hospital visits with pre-visit questionnaires and care plan templates
- **Insurance & Billing Assistant**: Tool to understand insurance coverage, estimate costs, and prepare billing documentation

### Caregiver Support

- **Care Coordination Hub**: Shared calendar and task board for multi-caregiver families with role assignments and status updates
- **Nutrition Planner**: Meal planning tool with CF-specific calorie/protein requirements, enzyme dosing guides, and grocery lists
- **School/Work Communication**: Templates and tools for communicating with schools and employers about CF needs and accommodations
- **Emergency Response Guide**: Interactive first-aid guide for common CF emergencies with step-by-step instructions

### Community & Resources

- **CF Wiki**: Collaborative knowledge base on CF treatments, medications, specialists, and research updates
- **Local Resources Directory**: Map-based directory of CF care centers, support groups, and community resources
- **Financial Aid Navigator**: Database of grants, scholarships, and financial assistance programs with eligibility filters
- **Parent Mentor Network**: Platform connecting experienced CF parents with new families for support and guidance

## 2. For CF Research Community

These projects focus on research infrastructure, data analysis, and scientific collaboration tools.

### Data Management

- **Research Data Registry**: Standardized metadata schema for CF research datasets with search and discovery
- **Longitudinal Study Tracker**: Tool for tracking patient outcomes over time with privacy-preserving data linkage
- **Biobank Inventory System**: Inventory management for biological samples with chain-of-custody tracking
- **Protocol Repository**: Standardized protocol templates and sharing platform for CF research methods

### Analysis & Visualization

- **Clinical Trial Simulator**: Model to simulate trial outcomes based on different patient populations and endpoints
- **Drug Response Predictor**: ML tool to predict individual responses to CFTR modulators based on genotype and biomarkers
- **Outcome Dashboard**: Real-time visualization of treatment outcomes across multiple CF centers
- **Literature Review Assistant**: AI-powered tool to summarize and categorize new CF research papers

### Collaboration & Infrastructure

- **Open Lab Notebook**: Transparent research platform for sharing methods, results, and negative findings
- **Multi-center Data Consortium**: Secure platform for sharing anonymized data across institutions with governance controls
- **Grant Collaboration Hub**: Tool for finding potential collaborators based on research interests and expertise
- **CF Data Standards**: Community-driven standards for data collection, sharing, and interoperability

### Patient-Centered Research

- **Patient-Reported Outcomes Platform**: Tool for collecting and analyzing patient-reported outcomes in real-world settings
- **Quality of Life Metrics**: Standardized QoL measures with culturally adapted versions for diverse populations
- **Community Priorities Registry**: Process for patients and families to prioritize research questions and funding areas
- **Trial Matchmaker**: Tool to match patients with appropriate clinical trials based on their profile and location

## Revolutionary ideas (advisory)

### Patient-Facing Revolutionary Concepts

- **AI Health Advocate**: Personal AI agent that learns patient's CF pattern, interacts with care team, and advocates for optimal treatment
- **Digital Twin Patient Model**: Predictive simulation of individual patient physiology for treatment optimization
- **Real-Time Lung Monitor**: Wearable sensor + ML model tracking lung function continuously without clinic visits
- **Microbiome Thermostat**: Personalized microbiome management system with daily probiotic recommendations

### Research Infrastructure Revolutionary Concepts

- **Decentralized Clinical Trials**: Blockchain-secured trial participation from home with wearable data integration
- **CF Genome Explorer**: Interactive visualization of CFTR variants and their functional impact across populations
- **Negative Results Repository**: Platform for sharing failed experiments and why they failed (reducing research waste)
- **CF Knowledge Graph**: AI-connected database linking genes, proteins, drugs, and clinical outcomes

### Public Good Infrastructure

- **Open CF Simulator**: Web-based physics simulator showing how CFTR modulators work at cellular level
- **CF Research Operating System**: Unified platform integrating data, tools, and collaboration for all CF research
- **Patient Data Commons**: Federated system where patients own their data and control sharing
- **Global CF Registry**: Real-time global surveillance of CF prevalence, treatments, and outcomes

## Implementation Guidelines

### For All Projects

1. **Privacy-first design**: Default to local-first data storage with optional cloud sync
2. **Open source**: All code should be open source with clear licenses
3. **Accessibility**: Follow WCAG 2.1 AA standards for web-based tools
4. **Modular architecture**: Build reusable components that can be shared across projects
5. **Documentation**: Comprehensive documentation for users, developers, and administrators

### Security Requirements

1. **No PHI in repositories**: Never commit patient data, even anonymized data
2. **Encryption at rest**: Sensitive data should be encrypted when stored
3. **Secure authentication**: Use established auth libraries with MFA support
4. **Regular security reviews**: Periodic security audits of all projects

## Next Steps

1. **Prioritize**: Rank projects by impact, feasibility, and alignment with CF community needs
2. **Research**: Conduct user research with patients, families, and researchers
3. **Prototype**: Build minimum viable products for top-priority projects
4. **Collaborate**: Engage with CF foundations, care centers, and advocacy groups

## Resources

- [Cystic Fibrosis Foundation](https://www.cff.org/)
- [ClinicalTrials.gov](https://clinicaltrials.gov/) for CF trials
- [CFTR2](https://cftr2.org/) for CFTR variant data
- [ORDIS](https://www.cff.org/Research/Researcher-Resources/ORDIS/) for CF research data

## Notes

- This is a living document—update as new ideas emerge
- Consider the "Grandmother Test": Would you be comfortable if this project was public?
- Always prioritize patient privacy and ethical considerations
- Focus on tools that fill gaps in the current CF ecosystem
