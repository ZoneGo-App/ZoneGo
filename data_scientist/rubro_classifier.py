"""
Business-category ("rubro") classifier from free-text descriptions.
Cheap, high-return second model(day 3 of the plan): a merchant types a free-text description when creating a campaing
("we sell empanadas and coffe every morning"), and this model normalizes that into one of the 
fixed categories the search filter uses - instead of forcing mechants into a dropdown
or leaving the search filter blind to typed-in text.

No rreal mechant descriptions exist yet, so this trains on a small synthetic
phrase bank (document as such - see DATA.md-style rreasoning). Swapping in real onboarding text later is a data change,
not a pipeline change: predict_rubro() takes any free-text string.


"""
import os
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.pipeline import Pipeline


#We store the necessary information in a variable to save the files required 
# for the final stage and generate them.
MODEL_PATH = os.path.join(os.path.dirname(__file__), "rubro_classifier.joblib")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "RUBRO_REPORT.md")

#We recalibrate before ordering another one with this variable.
CONFIDENCE_THRESHOLD = 0.22
OTHER_LABEL ="other"

# Synthetic phrase bank: a handful of realistic self-descriptions per
# category, the kind a merchant would type in an onboarding form. This is
# NOT real merchant text — it exists so the classifier has something to
# learn from before real descriptions start arriving.
#create dictionary
DESCRIPTIONS = {
    "bodega": [
        "Corner store open late selling snacks, chips and cold drinks",
        "We sell groceries, phone cards, lottery tickets and cigarettes",
        "Small neighborhood store with basic groceries and beer",
        "Convenience store, candy, soda, canned food and household items",
        "24 hour bodega with coffee, sandwiches and lottery",
        "Corner shop selling milk, bread, eggs and snacks",
        "We carry phone cards, snacks, drinks and toiletries",
        "Local bodega, cold beer, chips, and quick breakfast sandwiches",
        "Neighborhood store, groceries and household essentials",
        "Small store open all night, snacks and drinks",
        "Corner market with newspapers, snacks and cold soda",
        "Bodega cat, lottery tickets, and cold beer in the back",
        "We stock canned goods, cereal, milk and phone cards",
        "Late night corner store, snacks, drinks and cigarettes",
    ],
    "deli": [
        "We make sandwiches, cold cuts and salads to order",
        "Deli counter with fresh cut meats, cheeses and hero sandwiches",
        "Breakfast sandwiches, coffee and made to order lunch",
        "Fresh sandwiches, wraps and homemade soups every day",
        "Deli serving hot and cold sandwiches, salads and sides",
        "We slice deli meats and make custom sandwiches",
        "Sandwich shop with catering trays and daily specials",
        "Deli with fresh salads, sandwiches and rotisserie chicken",
        "Corner deli, egg sandwiches, coffee, catering platters",
        "Made to order sandwiches, wraps, and fresh juices",
        "Deli counter, cold cuts by the pound, hero sandwiches",
        "We do lunch specials, sandwiches, salads and soup of the day",
        "Sandwich and salad shop, catering for offices",
        "Bacon egg and cheese sandwiches, deli meats, coffee",
    ],
    "laundromat": [
        "Coin operated laundry with wash and fold service",
        "Self service laundromat, large capacity washers and dryers",
        "We offer wash dry fold and drop off laundry service",
        "Laundromat open 7 days, card and coin machines",
        "Wash and fold laundry service, same day pickup",
        "Self service washers and dryers, detergent for sale",
        "Laundry service, dry cleaning drop off, alterations",
        "Coin laundry with attendant, wash fold and delivery",
        "Large laundromat, industrial washers, folding service",
        "Neighborhood laundromat, wash dry fold, open late",
        "Laundry mat, coin and card machines, folding tables",
        "We wash, dry and fold, pickup and delivery available",
        "Self serve laundry, big machines for comforters",
        "Wash fold service, dry cleaning, and tailoring",
    ],
    "barbershop": [
        "Haircuts, beard trims and hot towel shaves for men",
        "Traditional barbershop, fades, line ups and shaves",
        "We do kids haircuts, fades and beard grooming",
        "Barbershop specializing in fades and design cuts",
        "Men's grooming, haircuts, shaves and beard trims",
        "Classic barbershop, walk ins welcome, fades and tapers",
        "Barber offering haircuts, shaves, and hot towel service",
        "Neighborhood barbershop, kids and adult haircuts",
        "Fades, beard trims, and straight razor shaves",
        "Barbershop with appointments and walk in haircuts",
        "We specialize in fades, tapers, and beard lineups",
        "Barbershop, men and boys haircuts, hot shaves",
        "Walk in barbershop, fades, designs, and beard trims",
        "Old school barbershop, straight razor shaves, haircuts",
    ],
    "pizzeria": [
        "We sell pizza by the slice, whole pies and calzones",
        "Italian pizzeria, thin crust pizza and pasta",
        "Pizza shop, pepperoni slices, garlic knots, calzones",
        "Wood fired pizza, pies and Italian specials",
        "Slice shop with cheese, pepperoni and specialty pizzas",
        "Family pizzeria, pizza pies, calzones and salads",
        "Pizza and pasta restaurant, delivery and takeout",
        "Neighborhood pizzeria, square slices and garlic bread",
        "We make fresh dough pizza, subs and calzones",
        "Pizzeria serving pies, slices, and Italian heroes",
        "Brick oven pizza, calzones, and garlic knots",
        "Pizza by the slice, whole pies, pasta dinners",
        "Family owned pizzeria, subs, calzones and salads",
        "Wood fired pies, slices, and Italian sandwiches",
    ],
    "coffee_shop": [
        "Espresso, lattes, cold brew and pastries",
        "Coffee shop with wifi, seating and fresh pastries",
        "We serve specialty coffee, tea and baked goods",
        "Cafe with espresso drinks, bagels and breakfast sandwiches",
        "Third wave coffee shop, pour over and cold brew",
        "Coffee and pastry shop, quiet seating for laptops",
        "Cafe serving lattes, croissants and iced coffee",
        "Neighborhood coffee shop, espresso bar and wifi",
        "We roast our own coffee, drip and espresso drinks",
        "Coffee shop with matcha, chai, and fresh muffins",
        "Espresso bar, cold brew, pastries and wifi",
        "Cafe with lattes, cappuccinos and fresh baked goods",
        "Coffee shop, pour over, espresso, and quiet seating",
        "Cafe serving drip coffee, tea, and breakfast pastries",
    ],
    "nail_salon": [
        "Manicures, pedicures and nail art",
        "Nail salon offering gel manicures and acrylics",
        "We do manicures, pedicures, waxing and nail art",
        "Full service nail salon, dip powder and gel polish",
        "Nail salon specializing in acrylics and nail design",
        "Manicure and pedicure services, walk ins welcome",
        "Nail art, gel polish, and spa pedicures",
        "Nail salon with waxing, manicures and pedicures",
        "We offer gel nails, acrylics, and nail repair",
        "Nail salon, classic and spa manicure pedicure packages",
        "Gel manicures, acrylics, dip powder and nail art",
        "Nail salon, waxing, pedicures and manicures",
        "Spa pedicures, gel polish, and nail extensions",
        "Manicure pedicure salon, walk ins and appointments",
    ],
    "hardware_store": [
        "Tools, paint, plumbing and electrical supplies",
        "Hardware store, we cut keys and mix paint",
        "We sell tools, hardware, and home repair supplies",
        "Hardware store with plumbing, electrical and paint",
        "Neighborhood hardware store, tools and key cutting",
        "We stock nails, screws, tools and paint supplies",
        "Hardware and paint store, plumbing fittings and tools",
        "Local hardware store, propane exchange and key cutting",
        "Hardware store selling tools, locks, and paint",
        "We carry hand tools, power tools and hardware supplies",
        "Hardware store, key cutting, screws, nails and paint",
        "Paint and hardware store, plumbing and electrical parts",
        "Tools, locks, and hardware for home repairs",
        "Hardware shop, propane, tools and paint mixing",
    ],
    
    OTHER_LABEL: [
        "We sell running sneakers and socks",
        "Sportswear and sneakers for everyone",
        "Flowers and plants for your home",
        "Florist, bouquets, plants and gift baskets",
        "I fix phones and sell chargers and cases",
        "Phone repair shop, screens, batteries and accessories",
        "Tattoo studio, walk ins welcome, custom designs",
        "Tattoo and piercing studio",
        "We sell bicycles and do repairs",
        "Bike shop, sales, repairs and rentals",
        "Pharmacy, prescriptions, vitamins and health products",
        "Drug store with prescriptions and over the counter medicine",
        "Pet grooming and dog food",
        "Pet store, grooming, food and supplies",
        "Shoe store selling sneakers, boots and sandals",
        "Clothing store, shirts, jeans and jackets",
        "Electronics store, phones, chargers and accessories",
        "Bookstore with new and used books",
        "Toy store for kids, games and puzzles",
        "Locksmith, keys, locks and car key fobs",
    ],
}


def build_dataset():
    texts, labels = [], []
    for rubro, phrases in DESCRIPTIONS.items():
        for phrase in phrases:
            texts.append(phrase)
            labels.append(rubro)
    return texts, labels


def train_rubro_classifier(random_state=42, test_size=0.25):
    texts, labels = build_dataset()

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=test_size, random_state=random_state, stratify=labels
    )

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, lowercase=True)),
        ("clf", LogisticRegression(max_iter=1000, random_state=random_state)),
    ])
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    f1_mac = f1_score(y_test, y_pred, average="macro", zero_division=0)
    report = classification_report(y_test, y_pred, zero_division=0)

    print(f"In-distribution accuracy (same phrase bank): {acc:.4f}")
    print(f"In-distribution F1-Macro: {f1_mac:.4f}")
    print(report)

    joblib.dump(pipeline, MODEL_PATH)
    print(f"\nModel saved to {MODEL_PATH}")

    # FIX (Problem #1, mitigation c): also measure and report what happens
    # on text that looks NOTHING like the training phrase bank, so the
    # README doesn't imply the 95%-style number generalizes to real
    # merchant text. This is exactly what a judge would test live.
    ood_results = evaluate_out_of_distribution(pipeline)

    def evaluate_out_of_distribution():
        return