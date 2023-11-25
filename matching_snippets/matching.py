from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from sklearn.metrics.pairwise import cosine_similarity
from data import ship_data as ships, cargo_data as cargoes

# Sample Ship and Cargo data

for ship in ships:
    ##add increasing id to each ship
    ship['id'] = ships.index(ship) + 1

for cargo in cargoes:
    ##add increasing id to each cargo
    cargo['id'] = cargoes.index(cargo) + 1

# Combine Ship and Cargo data for training Doc2Vec
documents = [TaggedDocument(words=str(ship['type']).split() + str(ship['body']).split(), tags=["ship_" + str(ship['id'])]) for ship in ships]
documents += [TaggedDocument(words=str(cargo['type']).split() + str(cargo['body']).split(), tags=["cargo_" + str(cargo['id'])]) for cargo in cargoes]

# Train Doc2Vec model
model = Doc2Vec(vector_size=100, window=5, min_count=1, workers=4, epochs=50)
model.build_vocab(documents)
model.train(documents, total_examples=model.corpus_count, epochs=model.epochs)

print("Model trained")
print(model.dv.vectors)

# Calculate similarity scores for cargoes
ship_id = 7  # Replace with the ship ID you want recommendations for
ship_vector = model.dv["ship_" + str(ship_id)].reshape(1, -1)
cargo_vectors = [model.dv["cargo_" + str(cargo['id'])].reshape(1, -1).flatten() for cargo in cargoes]
similarity_scores = cosine_similarity(ship_vector, cargo_vectors)

# Calculate similarity scores for ships
cargo_id = 6 # Replace with the cargo ID you want recommendations for
cargo_vector = model.dv["cargo_" + str(cargo_id)].reshape(1, -1)
ship_vectors = [model.dv["ship_" + str(ship['id'])].reshape(1, -1).flatten() for ship in ships]
similarity_scores_ships = cosine_similarity(cargo_vector, ship_vectors)

# Rank and recommend cargoes
ranked_cargoes = sorted(zip(cargoes, similarity_scores[0]), key=lambda x: x[1], reverse=True)
recommendations = [{"cargo": cargo, "similarity_score": score} for cargo, score in ranked_cargoes]

# Rank and recommend ships
ranked_ships = sorted(zip(ships, similarity_scores_ships[0]), key=lambda x: x[1], reverse=True)
recommendations_ships = [{"ship": ship, "similarity_score": score} for ship, score in ranked_ships]

# Print recommendations for ships
for recommendation in recommendations:
    print(f"Ship {ship_id} - Recommended Cargo: {recommendation['cargo']['id']} - Similarity Score: {recommendation['similarity_score']:.4f}")

# Print recommendations for cargoes
for recommendation in recommendations_ships:
    print(f"Cargo {cargo_id} - Recommended Ship: {recommendation['ship']['id']} - Similarity Score: {recommendation['similarity_score']:.4f}")
