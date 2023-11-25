from gensim.models import Word2Vec
from sklearn.feature_extraction.text import CountVectorizer
import numpy as np
from data import ship_data, cargo_data

# Assuming you have ship_data and cargo_data available
# (you can use the provided data or replace it with your actual data)

# Combine ship and cargo data for training
all_data = ship_data + cargo_data

# Extract text bodies and types for training
texts = [f"{obj['type']} {obj['body']}" for obj in all_data]

# Use CountVectorizer for text embedding
vectorizer = CountVectorizer()
text_embeddings = vectorizer.fit_transform(texts)

# Train Word2Vec model
word2vec_model = Word2Vec([text.split() for text in texts], vector_size=100, window=5, min_count=1, workers=4)

# Function to find top N similar objects for a given object index
def find_similar_objects(index, n=5):
    # Get the vector for the given object's text
    text_embedding = np.mean([word2vec_model.wv[word] for word in texts[index].split() if word in word2vec_model.wv], axis=0)

    # Check if the text_embedding is all zeros
    if np.all(text_embedding == 0):
        return []  # No similar objects if the embedding is all zeros
    
    # Calculate cosine similarity with other objects
    similarity_scores = word2vec_model.wv.similar_by_vector(text_embedding, topn=n)

    print(f"Similarity scores for '{texts[index]}': {similarity_scores}")

    # Filter objects of the opposite type
    opposite_type = 'cargo' if all_data[index]['type'] == 'ship' else 'ship'
    similar_objects = [obj for obj in all_data if obj['type'] == opposite_type and obj['body'] in [score[0] for score in similarity_scores]]

    return [(obj['type'], obj['body']) for obj in similar_objects]

# Example: Find top 3 similar cargos for the first ship
ship_index = 0
similar_cargos = find_similar_objects(ship_index, n=10)
print(f"Similar cargos to '{all_data[ship_index]['type']} {all_data[ship_index]['body']}':")
print(similar_cargos)