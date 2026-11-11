# Employee Analytics - Data Profile

## 1. Overview

- **Original IBM HR dataset:** 1,470 rows × 35 columns
- **Synthetic employee dataset:** 100,000 rows × 33 columns
- **Snapshot date:** 2025-12-31
- **Synthesis random seed:** 42

## Age

| Statistic | Original | Synthetic |
|---|---:|---:|
| Count | 1,470 | 100,000 |
| Mean | 36.92 | 37.04 |
| Median | 36.00 | 36.00 |
| Standard deviation | 9.14 | 9.13 |
| Minimum | 18.00 | 18.00 |
| Maximum | 60.00 | 60.00 |

## Monthly Income

| Statistic | Original | Synthetic |
|---|---:|---:|
| Count | 1,470 | 100,000 |
| Mean | 6502.93 | 6502.18 |
| Median | 4919.00 | 4924.00 |
| Standard deviation | 4707.96 | 4705.70 |
| Minimum | 1009.00 | 1009.00 |
| Maximum | 19999.00 | 19999.00 |

## Years at Company (Tenure)

| Statistic | Original | Synthetic |
|---|---:|---:|
| Count | 1,470 | 100,000 |
| Mean | 7.01 | 6.98 |
| Median | 5.00 | 5.00 |
| Standard deviation | 6.13 | 6.12 |
| Minimum | 0.00 | 0.00 |
| Maximum | 40.00 | 41.00 |

## Department Distribution

| Department | Original Count | Original % | Synthetic Count | Synthetic % |
|---|---:|---:|---:|---:|
| Human Resources | 63 | 4.29% | 4,255 | 4.25% |
| Research & Development | 961 | 65.37% | 65,248 | 65.25% |
| Sales | 446 | 30.34% | 30,497 | 30.50% |

## Attrition Distribution

| Employment Status | Original Count | Original % | Synthetic Count | Synthetic % |
|---|---:|---:|---:|---:|
| Active | 1,233 | 83.88% | 83,919 | 83.92% |
| Attrited | 237 | 16.12% | 16,081 | 16.08% |

## Structural Characteristics

- Total synthetic employees: 100,000
- Unique employee IDs: 100,000
- Unique employee codes: 100,000
- Unique email addresses: 100,000
- Employees without managers: 4,778
- Active employees: 83,919
- Attrited employees: 16,081

## Synthesis Methodology

The synthetic dataset was generated using the following approach:

1. Cleaned the original IBM HR dataset.
2. Applied whole-row resampling with replacement.
3. Applied controlled noise to selected numeric attributes, including age, tenure and income.
4. Redrew 10% of selected satisfaction, involvement and training records from their original empirical distributions.
5. Generated employee identities and deterministic email addresses using the Faker `en_IN` locale.
6. Derived dates using the fixed snapshot date.
7. Assigned managers within the same department with a strictly higher job level.
8. Used random seed 42 for reproducibility.

## Interpretation and Limitations

The synthetic dataset preserves the broad statistical and structural characteristics of the original IBM HR dataset while expanding it to 100,000 records.

The generated records are synthetic employees and must not be interpreted as actual additional IBM employees or historical employment events. The dataset is intended for data engineering, database design and analytics demonstrations.
