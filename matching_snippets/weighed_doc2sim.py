from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from sklearn.metrics.pairwise import cosine_similarity

# Sample Ship and Cargo data with additional fields
ships = [
    {"id": 1, "name": "Ship1", "details": "Ship details...", "port": "PortA", "location": "LocationX", "weight": 5000},
    {"id": 2, "name": "Ship2", "details": "Ship details...", "port": "PortB", "location": "LocationY", "weight": 8000}
]

cargoes = [
    {"id": 101, "name": "Cargo1", "details": "Cargo details...", "port": "PortA", "location": "LocationX", "weight": 6000},
    {"id": 102, "name": "Cargo2", "details": "Cargo details...", "port": "PortC", "location": "LocationZ", "weight": 7500}
]

# Define weights for each field
field_weights = {"name": 2, "details": 1, "port": 1.5, "location": 1.5, "weight": 1}

# Combine Ship and Cargo data for training Doc2Vec
documents = [
    TaggedDocument(
        words=sum(
            [int(field_weights[field]) * [field, str(ship[field]).lower()] for field in field_weights.keys()],
            []
        ),
        tags=["ship_" + str(ship['id'])]
    )
    for ship in ships
]

documents += [
    TaggedDocument(
        words=sum(
            [int(field_weights[field]) * [field, str(cargo[field]).lower()] for field in field_weights.keys()],
            []
        ),
        tags=["cargo_" + str(cargo['id'])]
    )
    for cargo in cargoes
]

# Train Doc2Vec model
model = Doc2Vec(vector_size=100, window=5, min_count=1, workers=4, epochs=50)
model.build_vocab(documents)
model.train(documents, total_examples=model.corpus_count, epochs=model.epochs)

# Calculate similarity scores
ship_id = 1  # Replace with the ship ID you want recommendations for
ship_vector = model.dv["ship_" + str(ship_id)].reshape(1, -1)
cargo_vectors = [model.dv["cargo_" + str(cargo['id'])].reshape(1, -1) for cargo in cargoes]
similarity_scores = cosine_similarity(ship_vector, cargo_vectors)

# Rank and recommend cargoes
ranked_cargoes = sorted(zip(cargoes, similarity_scores[0]), key=lambda x: x[1], reverse=True)
recommendations = [{"cargo": cargo, "similarity_score": score} for cargo, score in ranked_cargoes]

# Print recommendations
print("Recommendations for Ship", ship_id)
for recommendation in recommendations:
    print(f"Cargo {recommendation['cargo']['name']} - Similarity Score: {recommendation['similarity_score']:.4f}")
