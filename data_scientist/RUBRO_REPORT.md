# Rubro Classifier — ZoneGo

TF-IDF (word 1-2 grams) + Logistic Regression, trained on a synthetic
phrase bank (9 categories: bodega, deli, laundromat, barbershop, pizzeria, coffee_shop, nail_salon, hardware_store, other,
the last one being an explicit catch-all). NOT real merchant text yet —
see ml/DATA.md for why this project uses synthetic data and how it gets
swapped for real data later.

Train: 99 phrases · Test: 33 phrases.

## In-distribution metrics

- **Accuracy**: 0.9091
- **F1-Macro**: 0.9119

```
                precision    recall  f1-score   support

    barbershop       0.75      1.00      0.86         3
        bodega       1.00      0.67      0.80         3
   coffee_shop       1.00      1.00      1.00         4
          deli       0.75      0.75      0.75         4
hardware_store       1.00      1.00      1.00         4
    laundromat       1.00      1.00      1.00         3
    nail_salon       1.00      1.00      1.00         4
         other       0.80      0.80      0.80         5
      pizzeria       1.00      1.00      1.00         3

      accuracy                           0.91        33
     macro avg       0.92      0.91      0.91        33
  weighted avg       0.92      0.91      0.91        33

```

**These numbers are measured on phrases from the same synthetic phrase
bank used for training (same style, same vocabulary). They are NOT an
estimate of performance on real merchant-typed text — see the
out-of-distribution table below, which is.**

## Known limitation — out-of-distribution text

A confidence threshold (0.22) on `predict_proba()` now
routes anything the model isn't sure about to `other`, instead of forcing
it into the nearest-scoring wrong category. Tested on 8 real-sounding
descriptions of businesses outside the 8 rubros — none seen in training:

| Description | Predicted | Confidence |
|---|---|---|
| "We sell running sneakers and athletic wear" | `other` | 0.21 |
| "athletic shoes and sportswear" | `other` | 0.22 |
| "flowers and plants for your home" | `other` | 0.33 |
| "I fix phones and sell chargers" | `other` | 0.31 |
| "tattoo studio, walk ins welcome" | `other` | 0.16 |
| "we sell bicycles and do repairs" | `other` | 0.18 |
| "pharmacy, prescriptions and vitamins" | `other` | 0.27 |
| "pet grooming and dog food" | `other` | 0.24 |

If any row above shows a specific rubro (not `other`) with high confidence,
that is a real miss worth expanding the `other` phrase bank for, not a
threshold-tuning problem.

## Why this model, and what it's for

This is a cheap classifier that turns a merchant's free-text self-
description into a normalized category. It feeds the search filter: a
neighbor searching "coffee near me" gets matched by category even if the
merchant typed something free-form like "cafe with wifi and pastries"
instead of picking from a dropdown. Text that doesn't confidently match
any of the 8 rubros returns `other` instead of a wrong guess.

Usage:

```python
from rubro_classifier import predict_rubro
predict_rubro("We sell empanadas, coffee, and pastries every morning")
```
