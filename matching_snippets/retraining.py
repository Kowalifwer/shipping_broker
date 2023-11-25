from gensim.models.doc2vec import Doc2Vec, TaggedDocument

# Load the existing model
model = Doc2Vec.load("your_existing_model_path")

# Prepare new documents
new_documents = [
    TaggedDocument(words=["new", "document", "1"], tags=["new_doc_1"]),
    TaggedDocument(words=["new", "document", "2"], tags=["new_doc_2"]),
    # Add more new documents as needed
]

# Update vocabulary with new documents
model.build_vocab(new_documents, update=True)

# Train the model with new documents
model.train(new_documents, total_examples=model.corpus_count, epochs=50)

# Save the updated model
model.save("your_updated_model_path")
