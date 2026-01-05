import pandas as pd
import json

# Open the dataset
with open("recipes_for_cbrs.json", "r") as f:
    data = json.load(f)

flattened_data = []
for recipe in data:
    features = (
        recipe["features"]["ingredients"] +
        recipe["features"]["tags"] +
        recipe["features"]["kitchen"] +
        recipe["features"]["course"]
    )
    flattened_data.append({
        'id': recipe["id"],
        'title': recipe["title"],
        'content': features
    })

recipes_df = pd.DataFrame(flattened_data)

exploded = recipes_df.explode("content")


ingredient_matrix = pd.crosstab(exploded["id"], exploded["content"])



user_data = [
    {'id': 9518, 'rating': 4},
    {'id': 7835, 'rating': 5},
    {'id': 10952, 'rating': 3},
    {'id': 1403, 'rating': 4},
    {'id': 10741, 'rating': 4},
    {'id': 594, 'rating': 4},
    {'id': 10650, 'rating': 5},
    {'id': 6474, 'rating': 3},
    {'id': 995, 'rating': 4},
    {'id': 5704, 'rating': 2},
    {'id': 5543, 'rating': 3},
    {'id': 8954, 'rating': 1},
    {'id': 7021, 'rating': 3},
    {'id': 9063, 'rating': 5},
    {'id': 7253, 'rating': 2},
    {'id': 10589, 'rating': 2},
    {'id': 7797, 'rating': 2},
    {'id': 8745, 'rating': 4},
    {'id': 9407, 'rating': 2},
    {'id': 10418, 'rating': 3},
]

user_ratings_df = pd.DataFrame(user_data).set_index("id")
user_features_matrix = ingredient_matrix.loc[user_ratings_df.index]
user_profile = user_features_matrix.T.dot(user_ratings_df['rating'])

all_recipes_matrix = ingredient_matrix

recommendation_scores = (all_recipes_matrix.dot(user_profile) / user_profile.sum())
results = recipes_df[['id', 'title']].set_index('id')
results["score"] = recommendation_scores

print("\nUser profile")
print(user_profile.sort_values(ascending=False).head(10))

print("\nTop recommendations")
recommendations = results.drop(index=user_ratings_df.index)
print(recommendations.sort_values(by="score", ascending=False).head(10))