# Empirical Evaluation of Core Predictive Claims in Vedic Astrology (Jyotiṣa): Operationalization, Evidence, and Study Design

## Executive Summary

Vedic astrology (Jyotiṣa) continues to guide consequential decisions (health, marriage, career) with an implied promise of predictive reliability. This report frames a focused scientific question: **can core, widely taught Vedic astrological principles be operationalized into objective variables and empirically validated using standard statistical and forecasting criteria?** It does not assess astrology’s symbolic/spiritual value, counseling utility, or cultural significance; it evaluates *predictive and diagnostic* claims about measurable outcomes.

Across the provided evidence base, controlled and comparative quantitative studies generally report null or very small effects when astrology is tested under blinding and/or rule-based statistical comparisons—while qualitative ethnography helps explain why astrological consultations can still feel effective as meaning-making and therapeutic performances independent of literal predictive accuracy [90]. This report therefore emphasizes preregistration, transparent operationalization, multiplicity control, and replication as non-negotiable design constraints for any decisive empirical evaluation [10], [12], [27], [37].

## Main Findings

1. **The core research question is empirically addressable if astrology is translated into computable predictors and tested with modern prediction metrics** (calibration, discrimination, overall performance) rather than anecdotes [17]. Prior comparative studies illustrate this approach but report consistent null results in the tested rule-sets for cancer status and celebrity status [1], [11].

2. **Vedic astrology is historically and methodologically heterogeneous**, with multiple overlapping schools and toolkits (Parāśarī/BPHS [2], Jaimini [34], and Tājika annual astrology [71], [72]) and modern software-dependent computation that can materially alter derived chart variables (e.g., ayanāṃśa, nakṣatra, daśā start times) [74]. This heterogeneity is a key validity threat and must be addressed in operationalization and study governance.

3. **Practitioner claims can be reformulated as testable hypotheses**, especially for timing assertions (daśā/transit claims), using time-to-event methods that naturally match “when will it happen?” narratives and properly handle censoring [78], [79]. Forecasting claims should be evaluated out-of-sample against baselines [17].

4. **A pragmatic epistemic framework is appropriate**: admit to empirical synthesis only those claims with testable structure and stated failure conditions (falsifiability) [4], while treating metaphysical assertions as outside empirical adjudication unless they entail testable predictions [81]. Evidence grading and systematic review discipline (GRADE [36]; Cochrane-style protocol norms [38]; PRISMA 2020 [39]) and transparency mechanisms (preregistration and results-blind principles [37]) are central.

5. **A claim-matched portfolio of study designs is required**: (A) blinded prospective prediction studies for accuracy; (B) RCTs (individual or cluster) for decision impact; (C) case–control or nested case–control for rare outcomes, with explicit limitations about absolute risk estimation and calibration [22], [93], [97]. Blinding and allocation concealment are distinct protections and should be operationally safeguarded [91], [93], [94], [98].

6. **Data governance, linkage, and de-identification are first-order constraints**, especially given the need for birth time and location and linkage to event records. Operational approaches include common data models (OMOP) [26], regulatory-grade RWD documentation/validation practices [52], privacy-preserving linkage architectures where required [54], and risk-based de-identification framing (NIST) [19], including quasi-identifier control (k-anonymity family) [48]. Jurisdictional differences and certificate-era changes must be tracked (e.g., Montana [7], Washington [20]) and GDPR considerations may apply in some contexts [44].

7. **Decision rules must integrate practical significance (SESOI/MMES), statistical evidence beyond p-values, and replication criteria**, ideally locked via Registered Reports [10], [64], [65]. Equivalence testing supports “evidence of absence” for practically meaningful effects [33], [63], and Bayes factors (including replication Bayes factors) enable graded evidential claims [66], [67]. Replication planning is essential given observed effect-size shrinkage and variable replication rates in large replication exercises [32].

8. **Major confounds and validity threats include publication bias** [9], [30], self-selection [59], clustering/practitioner heterogeneity requiring multilevel/GEE modeling [60], [61], and multiplicity/analytic flexibility requiring preregistration and formal corrections [12], [27], [29].

## Detailed Analysis by Section

## Introduction and Research Question

Vedic astrology (Jyotiṣa) influences consequential decisions with confidence implying predictive reliability. The central question is: **can core claims be operationalized into objective variables and empirically validated using standard statistical and forecasting criteria?** The research question is framed as: **To what extent do foundational Vedic astrological principles yield predictions that are valid, falsifiable, and practically useful—when evaluated with mainstream empirical criteria such as statistical significance, effect size, calibration, and discrimination?**

Scope is restricted to **predictive claims about measurable human outcomes** where astrology is often invoked: health outcomes (including potential harm from incorrect guidance) [1], prominence/career “success” outcomes [11], and other life events tied to house/planet rules [1], [11]. The work explicitly excludes evaluation of astrology as symbolic/spiritual/therapeutic and excludes practitioner charisma or client satisfaction as evidence of predictive validity; these are distinct constructs. It further stresses why operationalization is necessary to prevent flexible post-hoc interpretation and selective recall from masquerading as accuracy.

Prior work demonstrates feasibility and the challenge: a cancer case–control comparison (254 cancer vs 498 long-life/no-cancer charts) reported no statistically significant positivity/negativity differences across tested entities and principles despite many tests [1]; a celebrity vs ordinary comparison (742 vs 509) likewise reported no tested fundamental principle differentiating groups [11]. These patterns motivate rigorous pre-specification, multiple-comparison control, and modern predictive validation metrics [17].

Key working definitions include operationalization, composite positivity/negativity scores as hypothesized predictors [1], [11], and “correctness” as empirical adequacy (reproducible predictive performance). Criteria for evidence include measurement validity categories [70], statistical inference with effect sizes and multiplicity correction [1], [11], and forecasting performance (calibration, discrimination/AUC, Brier score, decision-analytic net benefit) [17]. Falsifiability and ethics constraints motivate preregistration and transparency [13].

## Background: History, Concepts, and Practices of Vedic Astrology

Vedic astrology is historically layered, text-anchored, and heterogeneous rather than monolithic. Major streams include:

- **Parāśarī/BPHS-centered practice**, with extensive doctrine on planets, signs, aspects, strengths (*ṣaḍbala*), house judgments, yogas, divisional charts (*vargas*), and timing systems (*daśās*) [2]. BPHS functions as a practical toolbox, encouraging cumulative judgment across multiple indicators.
- **Jaimini system**, emphasizing sign-based period schemes and specialized derived lagnas (Upapada, Varnada) and distinctive daśās (Brahma, Rudra, Mahesvara) [34].
- **Tājika annual astrology**, a Sanskritized Perso-Arabic-influenced tradition. Scholarship identifies Arabic-source influence (e.g., Sahl ibn Bishr) on aspects/dignities and later Indian reinterpretations [71], with Balabhadra’s *Hāyanaratna* systematizing annual revolution computation, house judgments, aspects/dignities, and within-year periods [72].

Core concepts relevant for operationalization include:
- **Graha** (planets and nodes as indicators with benefic/malefic tendencies and strength doctrines) [2]
- **Rāśi** (sign context; primary timing units in some systems) [2], [34]
- **Nakṣatra** (important for micro-timing; software evaluation highlights computational sensitivity for nakṣatra/pāda and Vimshottari daśā calculations) [74]
- **Bhāva** (houses as life domains; BPHS provides extensive conditional outcome catalogs) [2]
- **Daśās** (timing engines central to prediction; multiple systems across schools) [34], [72]
- **Divisional charts (vargas)** and related strength assessments (*vimśopaka*) as resolution-enhancing lenses [2]

Contemporary practice is additionally shaped by software dependence and computational discrepancies. A comparative software analysis reports substantial variation versus a benchmark (accuracy rates 88% vs 51% vs 28% across programs in tested categories), including differences in ayanāṃśa, longitudes, nakṣatra/pāda, sunrise time, node positions, and crucially daśā/bhukti start times [74]. This makes computational standardization and provenance tracking essential for any empirical test.

## Claims and Testable Hypotheses

Practitioner discourse claims that natal features, daśā timing (especially Vimshottari), and transits predict both *whether* events occur and *when* they occur [75], [76], sometimes with very high asserted accuracy [77]. These can be translated into falsifiable hypotheses with explicit nulls and time-indexed outcomes, particularly via survival/time-to-event analysis with censoring [78], [79].

Four main hypothesis families:

**A) Daśā periods predict event timing**
- H1A: survival functions/hazards differ across daśā states  
- H0A: no hazard differences by daśā state  
Operationalize daśā as time-varying categorical exposure (mahadāśā/antardāśā) computed deterministically from birth data per Vimshottari rules [75], [76]. Analyze via Kaplan–Meier/log-rank and Cox models with time-varying covariates [78], [79].

**B) Transits trigger/modulate events conditional on natal promise**
- H1B: transit indicators and/or daśā×transit interactions associate with hazard  
- H0B: no such association  
Requires pre-specified transit feature computation and interaction tests [76].

**C) Natal placements/strength correlate with disease incidence**
- Case–control: H1C odds ratio ≠ 1 vs H0C odds ratio = 1  
- Cohort/survival: H1C’ hazard ratio ≠ 1 vs H0C’ hazard ratio = 1  
A precedent case–control design exists for cancer vs no-cancer charts [3], but interpretation depends critically on rule pre-specification and multiplicity control.

**D) Forecasting accuracy is high**
- H1D: astrology-derived model improves out-of-sample prediction vs baseline  
- H0D: no meaningful improvement  
Evaluation should use discrimination/calibration metrics and out-of-sample validation [17].

This section emphasizes that “predictive” versus “explanatory” targets differ: statistically detectable associations may still be useless for forecasting, so claims of practical predictive power require explicit forecasting evaluation.

## Philosophical and Epistemological Framework

The report adopts a pragmatic, pluralist stance: methods are chosen for dependable, decision-relevant inference. Evidence is graded using structured frameworks and transparent review methods: GRADE certainty domains [36], Cochrane-style protocol discipline [38], PRISMA 2020 reporting [39]. Hierarchies of evidence (e.g., AACN) [40] are treated as heuristics with caution that observational studies can outperform weak RCTs [82].

Falsifiability is a demarcation requirement: claims must specify risky predictions and failure conditions [4]. Anti-pseudoscience heuristics note that doctrines may mimic scientific form while immunizing themselves against refutation [81]. Operationally, only claims translatable into measurable variables, reproducible evaluation plans, and disconfirming evidence patterns are admitted to empirical grading.

Mechanisms are treated as useful insofar as they imply discriminating predictions and constrain model flexibility; they also inform transportability and indirectness judgments (a GRADE domain) [36]. Transparency tools—preregistration and results-blind principles—are treated as epistemic necessities even in observational/qualitative research when feasible [37]. Bayesian analyses require explicit priors, prior predictive assessment (e.g., prior predictive matching) [84], and sensitivity to priors, with structured prior-elicitation workflows recognized as difficult but necessary for auditability [83]. Where evidence is limited, structured expert knowledge elicitation can be used, following standardized protocols and documentation (EFSA EKE) [85].

Metaphysical assertions are bracketed: not “disproved” by empirical synthesis unless they entail testable predictions. Replication and convergent evidence are central to confidence, with thresholds and decision rules to be predeclared and sensitivity-tested.

## Literature Review: Previous Studies and Evidence

Two main literatures are distinguished:

1. **Quantitative controlled tests** treat astrology as falsifiable prediction and generally find chance-level or null performance under blinding/controls. Carlson’s double-blind matching study tested the natal-astrology thesis using CPI profiles; astrologers’ matching was not better than random [5]. A later reappraisal argues that alternative aggregation yields results near conventional significance with small effects [86], highlighting analytic flexibility and the importance of preregistered endpoints.

Rule-based Vedic comparative studies attempt to test specific principles: Rajopadhye et al. compare cancer vs no-cancer charts and frame results as questioning predictive accuracy for tested principles [88]. This study genre increases the premium on rule operationalization clarity, preregistration, and multiplicity control.

2. **Ethnographic/qualitative work** treats astrology as socially embedded practice. Avdeeff’s ethnography of Valluvar astrologers in Tamil Nadu documents performative/therapeutic efficacy: clients can feel relief and serenity after consultations through narrative, rhythm, authority, and culturally resonant meaning-making, independent of objective predictive truth [90]. This helps explain persistence and perceived “working” even if predictive accuracy is weak.

Critical appraisals argue astrology falls short of scientific standards compared with mature sciences [89], while practitioner-facing critiques dispute skeptical syntheses [87], underscoring the need for co-designed but preregistered and blinded studies to reduce later disputes [5], [86], [88], [90].

## Proposed Empirical Methodology

A claim-matched, preregistered portfolio is proposed with a common spine: pre-specification, representative sampling, unbiased allocation where intervening, blinding where feasible, and explicit replication/external validation planning [16], [22], [91], [93], [98].

**Design A: Blinded, prospective prediction study (registry-style)** for predictive validity. Predictions are time-stamped and not used for decisions during the primary accuracy phase; outcomes are ascertained later. Evaluation uses discrimination/calibration and decision-analytic complements [6], [17], with reporting aligned to prediction-model transparency norms (TRIPOD-family guidance) [96], [97]. Sampling aims for representativeness and addresses rare outcomes via pooling/enrollment extension; enrichment requires analytic weighting and external validation for calibration [22], [97].

**Design B: Randomized controlled trials** for decision impact (individual or cluster randomized). Allocation concealment is emphasized due to evidence that lack of concealment can bias estimated benefit [93], [94]. Blinding may be partial but should include blinded outcome adjudication and analyst blinding until SAP finalization [91], with governance safeguards to maintain blinding [98]. Time-to-event endpoints may use restricted mean time estimands with available power methods [92].

**Design C: Case–control / nested case–control studies** for rare outcomes, with careful control selection from the same source population [93]. Absolute risk and calibration require correction/recalibration and external validation [97].

Operational governance includes safeguards for adaptive/learning systems via “frozen model” confirmatory mode and “shadow-learning” exploratory mode, with versioning/audit trails and controlled interim access to prevent leakage and unblinding [98].

## Data Requirements and Operationalization

Testing requires: (1) natality data with birth time and location; (2) event records with timestamps and codes; (3) personality inventory data where relevant, plus provenance metadata.

Vital-record dictionaries illustrate structured DOB fields and restricted identifiers requiring DUAs (Montana) [7], while technical notes document geography variable complexities and known data quality issues (Washington) [20]. Event data should follow regulatory-grade conceptual vs operational definitions and validation expectations [52], with registry QA practices as a model [53]. Multi-part outcome operationalization is illustrated by CRS’s detailed fatality reporting dictionary structure [47].

Harmonization is planned via **OMOP CDM** with documented ETL conventions (PERSON table and birth timing conventions) [26], plus explicit mapping, code sets, time conventions, and geography conventions [52].

Quality assurance includes field-level plausibility checks, cross-source consistency checks, linkage quality estimation, and provenance tracking [52]. Privacy-preserving record linkage may be necessary when identifiers cannot be shared, with explicit linkage architecture and evaluation of error rates [54]. Data access requires DUAs for restricted fields [7] and structured registry access processes as exemplars [25]. IRB alignment requires specifying identifiability, harms, and security controls [99]. GDPR may apply even where HIPAA-style de-identification is assumed; “de-identified” may not mean “anonymous” under GDPR [44].

De-identification is treated as risk reduction (not elimination) per NIST [19], with quasi-identifier management via models like k-anonymity [48] and reporting controls such as small-cell suppression [7], [25]. A stepwise anonymization workflow is outlined, including pseudonymization, transformation of quasi-identifiers, and utility-preserving validation [19], [52].

## Statistical Analysis Plan

A credible SAP must be finalized before outcome examination and pre-specify estimands, endpoints, analysis populations, models, sample size justification, multiplicity control, and robustness checks. Regulatory guidance stresses prospective multiplicity planning and warns against false conclusions when multiple endpoints/analyses exist [12], [27].

Sample size planning should align with goals: SESOI-based frequentist power (example: \(f^2 = 0.016\), \(\alpha=.05\), power=.95 ⇒ \(N=1{,}378\)) [14]; simulation-based planning for Bayesian hierarchical models [28]; and assurance-based planning for prediction models to control optimism and achieve target performance [55].

Effect-size reporting includes point estimates and uncertainty intervals; Bayesian analyses require specified priors and decision criteria, planned via simulation for operating characteristics [28]. Clustering requires mixed models or robust marginal models, with ICC considerations in planning and sensitivity checks. Missing data strategies and protocol deviation handling must be pre-specified to avoid post hoc “most favorable” analysis choices [27].

Robustness checks (alternative covariate sets, functional forms, specification-curve style summaries, measurement error sensitivity) are pre-committed and reported regardless of direction to prevent selective reporting.

## Potential Confounds, Biases, and Validity Threats

Key threats include:

- **Publication bias/selective reporting**, which can distort effect sizes (example: antidepressant trials showing inflated published effects) [9]. Mitigation includes funnel plots/asymmetry tests [30], trim-and-fill as sensitivity [9], and selection models as sensitivity with strong assumptions [30].
- **Self-selection and confounding** in observational/self-recruited samples; volunteers can differ systematically (e.g., repeated paid study applicants showing higher personality disorder symptoms) [59]. Mitigation relies on protocol-driven design [29], documentation of recruitment/incentives, measured selection covariates, and pre-specified sensitivity analyses for unmeasured confounding [29].
- **Practitioner/site heterogeneity and clustering**, which if ignored inflates Type I error and misstates precision [60]. Mitigation includes multilevel models or GEE [60] and design-stage planning for cross-level interactions and adequate cluster counts [61].
- **Multiplicity and analytic flexibility**, interacting with publication bias. Mitigation is procedural: preregistration and explicit outcome/test hierarchies, plus appropriate error control and clear labeling of exploratory analyses [12], [27], [29].

External validity concerns are addressed via careful recruitment reporting and, where feasible, transportability approaches (e.g., reweighting toward target populations) as part of protocol-driven observational design [29].

## Interpretation Criteria and Decision Rules

Interpretation criteria should be pre-specified and integrate practical significance, graded statistical evidence, and replication rules. Registered Reports (in-principle acceptance prior to outcomes) reduce p-hacking and HARKing and require explicit “interpreting results” plans [10], [64], [65]. SESOI/MMES acts as a gatekeeper against conflating statistical significance with importance [63]; SESOI can be justified using anchor-based methods where applicable [63] and should inform power planning [14].

Statistical evidence should go beyond p-values: effect sizes with intervals, equivalence tests for negligible effects [63], and Bayes factors (including replication Bayes factors) to quantify evidence for/against hypotheses [66], [67]. Replication success should be defined prospectively; large replication efforts show variable replication rates and effect-size shrinkage (replication effects averaging 45% of originals in one set) [32]. Decision triage rules define support/partial support/rejection, emphasizing that “rejection” typically means rejecting practically meaningful effects (evidence consistent with negligible range), not necessarily any nonzero association [33], [63].

## Ethical, Cultural, and Communication Considerations

No evidence items were provided for this section, so it remains evidence-neutral and avoids unsupported claims. It outlines general ethical issues when studying beliefs: risks of distress, stigma, privacy harms, power dynamics, and the need for respectful framing, robust consent as a process, debriefing where deception is used, and careful communication to prevent misinterpretation or stigmatization. It recommends transparent reporting of uncertainty and practical significance and emphasizes culturally sensitive measurement and community engagement. (No inline citations are included in this section because none were provided.)

## Limitations, Feasibility, and Resource Assessment

No evidence sources were provided for project-specific feasibility, budget, timelines, or quantitative resource estimates, so the section remains a structured template identifying feasibility drivers (access, operational, analytic, ethical/legal) and limitation types (internal validity, external validity, statistical precision, implementation burden). It provides placeholder tables for budgets, timelines, and risk registers, and lists what inputs are required to finalize the section with defensible, cited quantitative estimates.

## Conclusions, Recommendations, and Next Steps

No results are provided, so no empirical conclusion about whether Vedic astrology’s predictive claims are supported can be drawn. What can be concluded from the present materials is methodological: **core predictive claims are testable when translated into pre-specified computable variables, evaluated with modern prediction metrics and time-to-event methods, and protected against multiplicity and bias via preregistration, blinding, and replication** [10], [12], [17], [27], [78], [79].

Process-recommendations follow from the framework: finalize operational definitions, preregister hypotheses and SAP, standardize computation (including software/ayanāṃśa choices) [74], secure high-quality linked event datasets with documented linkage error [52], [54], and implement replication/external validation plans [16], [97]. For high-stakes applications (e.g., health), decision-impact claims require RCT evidence rather than accuracy alone [22], [93].

## Sources

[1] https://www.allresearchjournal.com/archives/2021/vol7issue5/PartB/7-5-6-895.pdf — *[PDF] Empirical testing of few fundamental principles of Vedic astrology through comparative analysis of astrological charts of cancer diseased persons versus persons who never had it*  
[2] https://storage.yandexcloud.net/j108/library/hr6fkynz/Maharishi_Parashara_-_Brihat_Parasara_Hora_Sastra_(Vol._1).pdf — *Parasara Sastra Hora*  
[3] https://www.academia.edu/48934562/Empirical_testing_of_few_fundamental_principles_of_Vedic_astrology_through_comparative_analysis_of_astrological_charts_of_cancer_diseased_persons_versus_persons_who_never_had_it — *Empirical testing of few fundamental principles of Vedic astrology through comparative analysis of astrological charts of cancer diseased persons versus persons who never had it*  
[4] https://www.britannica.com/topic/philosophy-of-science/Eliminativism-and-falsification — *Philosophy of science - Eliminativism, Falsification, Theory | Britannica*  
[5] https://scispace.com/pdf/a-double-blind-test-of-astrology-1lfssa2u99.pdf — *[PDF] A double-blind test of astrology - SciSpace*  
[6] https://pmc.ncbi.nlm.nih.gov/articles/PMC6460552/ — *Methods for Evaluation of medical prediction Models, Tests ...*  
[7] https://dphhs.mt.gov/assets/publichealth/Epidemiology/VSU/MONTANADATADICTIONARYFORBIRTHRECORDS_2023.pdf — *[PDF] Data Dictionary for Montana Birth Records - Dphhs*  
[8] https://www.fda.gov/files/drugs/published/Multiple-Endpoints-in-Clinical-Trials-Guidance-for-Industry.pdf — *[PDF] Multiple Endpoints in Clinical Trials Guidance for Industry | FDA*  
[9] https://pmc.ncbi.nlm.nih.gov/articles/PMC6571372/ — *The trim-and-fill method for publication bias*  
[10] https://shs.hal.science/halshs-03897719/file/Guide%20to%20RR%20for%20economists.pdf — *[PDF] A Practical Guide to Registered Reports for Economists - HAL-SHS*  
[11] https://www.jyotishajournal.com/pdf/2021/vol6issue1/PartB/6-1-19-949.pdf — *[PDF] Comparison of Vedic astrology birth charts of celebrities with ordinary people: An empirical study*  
[12] https://www.fda.gov/media/162416/download — *[PDF] Multiple Endpoints in Clinical Trials - Guidance for Industry - FDA*  
[13] https://scientificresearchjournal.com/wp-content/uploads/2024/01/social-science-vol-10-788-813.pdf — *Scientific and Ethical Dimensions of Astrology*  
[14] https://shiny.ieis.tue.nl/examples/SESOI_examples.html — *Examples of specifying a smallest effect size of interest*  
[15] https://aspe.hhs.gov/sites/default/files/documents/e43417753fc9c1afd3d798c16b938751/astho-prams-data-linkage-framework-final.pdf — *[PDF] A Framework for Linking PRAMS with Administrative Data - ASPE*  
[16] https://publications.aston.ac.uk/id/eprint/48049/1/Handbook-for-Reproduction-and-Replication-Studies_v1.0.pdf — *[PDF] Handbook for Reproduction and Replication Studies*  
[17] https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3575184/ — *Assessing the performance of prediction models: a framework for some traditional and novel measures*  
[18] https://www.academia.edu/48934562/Empirical-testing_of_few_fundamental_principles_of_Vedic_astrology_through_comparative_analysis_of_astrological_charts_of_cancer_diseased_persons_versus_persons_who_never_had_it  
[19] https://nvlpubs.nist.gov/nistpubs/ir/2015/nist.ir.8053.pdf — *[PDF] De-Identification of Personal Information*  
[20] https://doh.wa.gov/sites/default/files/2023-12/422-160-BirthDataFileTechnicalNotes.pdf — *[PDF] Birth Data File Technical Notes*  
[21] https://pmc.ncbi.nlm.nih.gov/articles/PMC6290666/ — *A Prospective Longitudinal Study of Marriage from Midlife to Later Life*  
[22] https://dl.icdst.org/pdfs/files3/44a3fc10fc9813ae7e78d50f33a14793.pdf — *[PDF] PCORI METHODOLOGY REPORT*  
[23] https://pmc.ncbi.nlm.nih.gov/articles/PMC8012078/  
[24] https://www.mississippi.edu/sites/default/files/ihl/files/Data%20Dictionary%20Complete%20rev090525%20Sept2025.pdf  
[25] https://www.perinatalservicesbc.ca/Documents/Data-Surveillance/PDR/DataRequests/DAR_FAQ.pdf — *[PDF] BC Perinatal Data Registry (PDR) Data Access Requests (DAR) for ...*  
[26] https://ohdsi.github.io/CommonDataModel/cdm54.html — *OMOP CDM v5.4 - GitHub Pages*  
[27] https://ema.europa.eu/en/documents/scientific-guideline/points-consider-multiplicity-issues-clinical-trials_en.pdf — *[PDF] Points to consider on multiplicity issues in clinical trials*  
[28] https://research.tilburguniversity.edu/en/publications/sample-size-determination-for-bayesian-hierarchical-models-common  
[29] https://effectivehealthcare.ahrq.gov/sites/default/files/related_files/user-guide-observational-cer-130113.pdf — *Developing a Protocol for Observational Comparative Effectiveness Research: A User's Guide*  
[30] https://pmc.ncbi.nlm.nih.gov/articles/PMC5953768/ — *Quantifying Publication Bias in Meta-Analysis*  
[31] https://hal.science/hal-04943071v2/file/Pre-registration-for-Economists-exhaustive-templates-for-primary-and-secondary-data.pdf  
[32] https://www.nature.com/articles/s41562-024-02062-9 — *Examining the replicability of online experiments selected by a decision market*  
[33] https://eLife.org/articles/92311 — *Replication of null results: Absence of evidence or evidence of absence?*  
[34] https://books.google.com/books/about/Jaiminisutras.html?id=Kz4vEAAAQBAJ — *Jaiminisutras: English Translation with full Notes and Original Texts ...*  
[35] https://ssha2022.ssha.org/uploads/220655 — *LIFE-M: The Longitudinal, Intergenerational Family Electronic Micro-Database Project*  
[36] https://www.cdc.gov/acip-grade-handbook/hcp/chapter-7-grade-criteria-determining-certainty-of-evidence/index.html — *Chapter 7: GRADE Criteria Determining Certainty of ...*  
[37] https://poli.cms.arts.ubc.ca/wp-content/uploads/sites/31/2019/01/Jacobs-Prereg-and-RBR-in-Qualitative-and-Observational-1.pdf — *[PDF] 1 Of Bias and Blind Selection: Pre-registration and Results-Free Review in Observational and Qualitative Research*  
[38] https://www.cochrane.org/sites/default/files/uploads/PDFs/guide_to_the_contents_of_a_cochrane_methodology_protocol_and_review.pdf — *Guide to the contents of a Cochrane Methodology protocol and review*  
[39] https://pmc.ncbi.nlm.nih.gov/articles/PMC8008539/ — *The PRISMA 2020 statement: an updated guideline for ... - PMC*  
[40] https://www.aacn.org/clinical-resources/practice-alerts/aacn-levels-of-evidence — *AACN Levels of Evidence*  
[41] https://pubmed.ncbi.nlm.nih.gov/17234565/  
[42] https://www.cos.io/blog/introducing-the-theory-based-predictions-in-social-science-preregistration-template-qa-with-andrew-cesare-miller  
[43] https://aiimpacts.org/evidence-on-good-forecasting-practices-from-the-good Judgment Project/ — *Evidence on good forecasting practices from the Good Judgment Project*  
[44] https://research.cuanschutz.edu/docs/librariesprovider148/comirb_documents/guidance/gdpr-guidance.pdf?sfvrsn=a2172fb9_12 — *General Data Protection Regulation (GDPR) and Human Subjects Research*  
[45] https://cdn.wou.edu/institutionalresearch/files/2024/02/20170429-Scarf-Data-Dictionary-2013.pdf  
[46] https://www.mississippi.edu/sites/default/files/ihl/files/datadictionary_complete_102324.pdf  
[47] https://ncfrp.org/wp-content/uploads/DataDictionary_CRS_v6-0.pdf — *Data Dictionary*  
[48] https://utrechtuniversity.github.io/dataprivacyhandbook/k-l-t-anonymity.html — *K-anonymity, l-diversity and t-closeness | Data Privacy Handbook*  
[49] https://www.dohealth.ae/-/media/Feature/Resources/Guidelines/DOH-Guideline-on-RWD_RWE-based-clinical-research.ashx  
[50] https://www.censinet.com/perspectives/top-frameworks-gdpr-data-de-identification  
[51] https://catalogues.ema.europa.eu/system/files/2024-02/ARGX-113-PAC-2206-EU%20Protocol-V2.0_fully%20signed-including%20annex4_Redacted.pdf  
[52] https://www.fda.gov/media/152503/download — *[PDF] Assessing Electronic Health Records and Medical Claims Data to ...*  
[53] https://effectivehealthcare.ahrq.gov/sites/default/files/registries-guide-3rd-edition-vol-2-140430.pdf — *[PDF] A User's Guide Registries for Evaluating Patient Outcomes*  
[54] https://www.nia.nih.gov/sites/default/files/2023-08/pprl-linkage-strategies-preliminary-report.pdf — *[PDF] Privacy Preserving Record Linkage (PPRL) Strategy and Recommendations*  
[55] https://arxiv.org/pdf/2602.23507 — *[PDF] Sample Size Calculations for Developing Clinical Prediction Models*  
[56] https://lakens.github.io/statistical_inferences/08-samplesizejustification.html  
[57] https://www.mdpi.com/2076-3417/15/1/210  
[58] https://www.aje.com/arc/assessing-and-avoiding-publication-bias-in-meta-analyses  
[59] https://pmc.ncbi.nlm.nih.gov/articles/PMC9994707/ — *Self-selection biases in psychological studies: Personality and*  
[60] https://pmc.ncbi.nlm.nih.gov/articles/PMC11469681/ — *Using Multilevel Models and Generalized Estimating Equation ...*  
[61] https://hermanaguinis.com/pdf/JOMcrosslevel.pdf — *[PDF] Best-Practice Recommendations for Estimating Cross-Level Interaction Effects Using Multilevel Modeling*  
[62] https://support.sas.com/resources/papers/proceedings13/433-2013.pdf  
[63] https://pdfs.semanticscholar.org/5ec8/b805acdf7ee973d7bc55bd6583cc008b8494.pdf — *Using Anchor-Based Methods to Determine the Smallest ...*  
[64] https://www.cos.io/initiatives/registered-reports — *Registered Reports - Center for Open Science*  
[65] https://think.f1000research.com/wp-content/uploads/2020/08/Registered_Reports_Stage_One_Study_Protocol_Template_for_authors.pdf — *[PDF] Registered Reports - F1000 Research*  
[66] https://pmc.ncbi.nlm.nih.gov/articles/PMC6877488/ — *Replication Bayes factors from evidence updating - PMC*  
[67] https://pmc.ncbi.nlm.nih.gov/articles/PMC8258966/ — *Bayesian updating: increasing sample size during the course ...*  
[68] https://osf.io/registered-reports  
[69] https://www.psychreg.org/article/minimally-meaningful-effect-size-pre-registrations-mm...  
[70] https://www.scribbr.com/methodology/types-of-validity/ — *The 4 Types of Validity in Research | Definitions & Examples*  
[71] https://www.academia.edu/43648520/Origins_of_the_T%C4%81jika_System_of_Astrological_Aspects_and_Dignities — *Origins of the Tajika System of Astrological Aspects and Dignities*  
[72] https://library.oapen.org/bitstream/id/c11056f5-5abd-49e0-ab27-3e4f12a8e728/9789004433717.pdf — *The Jewel of Annual Astrology - OAPEN Library*  
[73] https://ia902304.us.archive.org/28/items/in.ernet.dli.2015.134405/2015.134405.Jaiminisutras-English-Translation.pdf  
[74] https://www.academia.edu/128386692/An_empirical_analysis_of_positional_accuracy_and_computational_precision_A_comparative_study_of_modern_Vedic_astrology_software  
[75] https://goodstarsjyotish.substack.com/p/vimshottari-dasha-understanding-vedic  
[76] https://lakshminarayanlenasia.com/articles/Predictive-jyotish-by-m-n-kedaar.pdf  
[77] https://medium.com/@ranjanpal9/a-simple-approach-to-demystify-timing-of-events-in-vedic-astrology-974f1af92671  
[78] https://christofseiler.github.io/stats205/Lecture19/Life.pdf — *[PDF] Time to Event Analysis (Part 1) - Christof Seiler ty*  
[79] https://pmc.ncbi.nlm.nih.gov/articles/PMC10957029/ — *Survival Analysis 101: An Easy Start Guide to Analyzing Time-to-Event Data*  
[80] https://digitalcommons.usu.edu/cgi/viewcontent.cgi?article=2110&context=etd  
[81] https://plato.stanford.edu/entries/pseudo-science/ — *Science and Pseudo-Science - Stanford Encyclopedia of Philosophy*  
[82] https://content.leg.colorado.gov/sites/default/files/r25-1161-the-hierarchy-of-health-research-evidence-accessible.pdf  
[83] https://paulbuerkner.com/publications/pdf/2023__Mikkola_et_al__Bayesian_Analysis.pdf — *[PDF] Prior Knowledge Elicitation: The Past, Present, and Future*  
[84] https://jmlr.org/papers/volume24/21-0623/21-0623.pdf — *[PDF] Prior Specification for Bayesian Matrix Factorization via Prior Predictive Matching*  
[85] https://www.efsa.europa.eu/sites/default/files/consultation/130813.pdf — *[PDF] Guidance on Expert Knowledge Elicitation in Food and Feed Safety Risk Assessment*  
[86] https://correlationjournal.com/the-carlson-test-continues-to-support-astrology/  
[87] https://correlationjournal.com/review-understanding-astrology/  
[88] https://www.semanticscholar.org/paper/Empirical-testing-of-few-fundamental-principles-of-Rajopadhye-Rajopadhye/ffdfefe5eaa69d682c2e8fef14a5c41c7e1bbb63  
[89] https://www.ijrah.com/vol-3-4-1  
[90] https://asianethnology.scholasticahq.com/article/154583  
[91] https://pmc.ncbi.nlm.nih.gov/articles/PMC8308085/ — *Blinding in Clinical Trials: Seeing the Big Picture*  
[92] https://pmc.ncbi.nlm.nih.gov/articles/PMC10473860/ — *Power and Sample Size Calculations for the Restricted Mean Time ...*  
[93] https://pmc.ncbi.nlm.nih.gov/articles/PMC6743387/ — *Selection of Control, Randomization, Blinding, and Allocation ... - PMC*  
[94] https://pmc.ncbi.nlm.nih.gov/articles/PMC10558187/ — *Impact of Allocation Concealment and Blinding in Trials Addressing ...*  
[95] https://bmjopen.bmj.com/content/11/7/e048008  
[96] https://www.tripod-statement.org/wp-content/uploads/2024/04/TRIPOD-SRMA-1.pdf  
[97] https://www.bmj.com/content/381/bmj-2022-073538  
[98] https://www.acrohealth.org/wp-content/uploads/2025/01/Safeguard-Blinding-in-Data-Governance-ACROTransCelerateResource.pdf  
[99] https://admindatahandbook.mit.edu/book/v1.0/irb.html  
[100] https://admindatahandbook.mit.edu/print/v1.0/handbook_ch4_IRB.pdf