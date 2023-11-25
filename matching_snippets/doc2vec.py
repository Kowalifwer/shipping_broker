from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from data import ship_data, cargo_data

# Assuming ship_data and cargo_data are lists of ship and cargo objects
ship_documents = [TaggedDocument(words=str(ship), tags=[f"ship_{ship_id}"]) for ship_id, ship in enumerate(ship_data)]
cargo_documents = [TaggedDocument(words=str(cargo), tags=[f"cargo_{cargo_id}"]) for cargo_id, cargo in enumerate(cargo_data)]

# Combine ship and cargo documents
all_documents = ship_documents + cargo_documents

# Train the Doc2Vec model
model = Doc2Vec(vector_size=100, window=5, min_count=1, workers=4, epochs=20)
model.build_vocab(all_documents)
model.train(all_documents, total_examples=model.corpus_count, epochs=model.epochs)

# Get the vector representation of a ship or cargo (example using the first ship)
ship_vector = model.dv["ship_0"]

# Find most similar ships or cargos based on the vector representation
similar_ships = model.dv.most_similar("ship_0", topn=5)
print(similar_ships)
