import re
import json
import os
from collections import Counter
from datetime import datetime, timezone
import torch # type: ignore
import torch.nn as nn # type: ignore
import torch.optim as optim # type: ignore
from torch.utils.data import DataLoader, TensorDataset # type: ignore

# Part A: parameter limit calculation
def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

# Part B: data preprocessing
def clean_text(text):
    """lowercase, remove non-alphabetic chars, split, filter short words"""
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    words = text.split()
    words = [w for w in words if len(w) > 1]
    return words

def build_vocab(abstracts, max_vocab_size=5000):
    #creates vocab from the abstract list
    #counts word freq with counter
    counter = Counter()
    for abs_text in abstracts:
        counter.update(clean_text(abs_text))
    most_common = counter.most_common(max_vocab_size)
    vocab_to_idx = {w: i + 1 for i, (w, _) in enumerate(most_common)} # dict word:index
    idx_to_vocab = {i + 1: w for i, (w, _) in enumerate(most_common)} #dic index:word
    return vocab_to_idx, idx_to_vocab, counter


def encode_bow(text, vocab_to_idx, vocab_size):
    # convert str in a vector 
    # for each known word, increments iots index
    vec = torch.zeros(vocab_size)
    for w in clean_text(text):
        idx = vocab_to_idx.get(w, 0)  # 0 = unknown
        if idx > 0:
            vec[idx - 1] += 1.0
    return vec


# Part C: autoencoder architecture
class TextAutoencoder(nn.Module):
    def __init__(self, vocab_size, hidden_dim, embedding_dim):
        super().__init__() # initializes parent nn.Module class

        #encoder part
        self.encoder = nn.Sequential(
            nn.Linear(vocab_size, hidden_dim), #input covab_size, output: hidden size
            nn.ReLU(),  # ReLu activation
            nn.Linear(hidden_dim, embedding_dim), # vconnected layer. hidden size -> embedding sizae
        )

        # decoder part
        self.decoder = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim), #connected layer: embedding size /> hidden size
            nn.ReLU(),
            nn.Linear(hidden_dim, vocab_size),
            nn.Sigmoid(), # sigmoid activation
        )

    def forward(self, x):
        embedding = self.encoder(x) #pass inpuit through the encoder to get compression
        reconstruction = self.decoder(embedding) # pass embedding thoruh decodeer to reconstruct
        return reconstruction, embedding


# Part D: Training Implementation
def train_autoencoder(
    input_file,
    output_dir,
    epochs=50,
    batch_size=32,
    hidden_dim=256,
    embedding_dim=64,
):
    # Load data
    # --- Load abstracts from JSON file ---
    with open(input_file, "r", encoding="utf-8") as f:
        papers = json.load(f) #list of papers
    abstracts = [p["abstract"] for p in papers]

    # Build vocabulary
    vocab_to_idx, idx_to_vocab, counter = build_vocab(abstracts, max_vocab_size=5000)
    vocab_size = len(vocab_to_idx)
    print(f"Vocabulary size: {vocab_size}")

    # Encode abstracts to bag
    bow_vectors = [encode_bow(a, vocab_to_idx, vocab_size) for a in abstracts]
    data = torch.stack(bow_vectors) #stack in a tensor

    #dataset, the input = target
    dataset = TensorDataset(data, data)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Build model
    model = TextAutoencoder(vocab_size, hidden_dim, embedding_dim)
    total_params = count_parameters(model) # count parmeters
    print(f"Total parameters: {total_params}")
    if total_params > 2_000_000: #constraint
        raise ValueError("Model exceeds 2M parameter limit!")

    #device/ training components
    device = torch.device("cpu")
    model.to(device)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3)

    # Train loop
    start_time = datetime.now(timezone.utc).isoformat()
    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        for batch_x, _ in dataloader: 
            batch_x = batch_x.to(device)
            optimizer.zero_grad()  #reset gradient
            recon, _ = model(batch_x) #fordward pass
            loss = criterion(recon, batch_x) # compares the reconstruction
            loss.backward() # backpropagation
            optimizer.step() # updates model weights
            total_loss += loss.item() 
        avg_loss = total_loss / len(dataloader)
        if epoch % 10 == 0 or epoch == 1 or epoch == epochs:
            print(f"Epoch {epoch}/{epochs}, Loss: {avg_loss:.4f}")

    end_time = datetime.now(timezone.utc).isoformat() # log training

    # save outputs
    os.makedirs(output_dir, exist_ok=True)

    # save model
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "vocab_to_idx": vocab_to_idx,
            "model_config": {
                "vocab_size": vocab_size,
                "hidden_dim": hidden_dim,
                "embedding_dim": embedding_dim,
            },
        },
        os.path.join(output_dir, "model.pth"),
    )

    # Save embeddings
    embeddings_out = []
    with torch.no_grad(): # disables gradient tracking
        for p in papers:
            bow = encode_bow(p["abstract"], vocab_to_idx, vocab_size).unsqueeze(0)
            recon, emb = model(bow)
            loss = criterion(recon, bow) # reconstruction
            embeddings_out.append(
                {
                    "arxiv_id": p["arxiv_id"],
                    "embedding": emb.squeeze().tolist(), #embedding vector list
                    "reconstruction_loss": float(loss.item()), # reconstruction quality 
                }
            )
    with open(
        os.path.join(output_dir, "embeddings.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(embeddings_out, f, indent=2)

    # save vocab
    vocab_data = {
        "vocab_to_idx": vocab_to_idx,
        "idx_to_vocab": idx_to_vocab,
        "vocab_size": vocab_size,
        "total_words": sum(counter.values()),
    }
    with open(
        os.path.join(output_dir, "vocabulary.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(vocab_data, f, indent=2)

    # Save training log
    log_data = {
        "start_time": start_time,
        "end_time": end_time,
        "epochs": epochs,
        "final_loss": avg_loss,
        "total_parameters": total_params,
        "papers_processed": len(papers),
        "embedding_dimension": embedding_dim,
    }
    with open(
        os.path.join(output_dir, "training_log.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(log_data, f, indent=2)

    print("Training complete. Files saved to:", output_dir)


# Part E: script entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="Path to papers.json")
    parser.add_argument("output_dir", help="Directory to save outputs")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=32)
    args = parser.parse_args()

    train_autoencoder(
        args.input_file,
        args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )