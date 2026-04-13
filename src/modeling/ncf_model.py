import torch
import torch.nn as nn
from typing import List

class NeuralCollaborativeFiltering(nn.Module):
    """
    Neural Collaborative Filtering (NCF) Model.
    
    This architecture utilizes user and item embeddings, concatenates them,
    and passes the resulting latent vector through a Multi-Layer Perceptron (MLP).
    It is designed for implicit feedback optimized via binary classification.
    """

    def __init__(
        self, 
        num_users: int, 
        num_items: int, 
        embedding_dim: int = 64, 
        hidden_layers: List[int] = [128, 64, 32], 
        dropout_rate: float = 0.2
    ) -> None:
        """
        Initializes the NCF model.

        Args:
            num_users (int): Total number of unique users in the dataset.
            num_items (int): Total number of unique items (songs) in the dataset.
            embedding_dim (int, optional): Size of the latent dimension for embeddings. Defaults to 64.
            hidden_layers (List[int], optional): Number of neurons in each hidden layer of the MLP. 
                                                 Defaults to [128, 64, 32].
            dropout_rate (float, optional): Dropout probability for regularization. Defaults to 0.2.
        """
        super(NeuralCollaborativeFiltering, self).__init__()

        # Embedding layers
        self.user_embedding = nn.Embedding(num_embeddings=num_users, embedding_dim=embedding_dim)
        self.item_embedding = nn.Embedding(num_embeddings=num_items, embedding_dim=embedding_dim)

        # Multi-Layer Perceptron (MLP) components
        mlp_modules = []
        input_dim = embedding_dim * 2  # Concatenation of User and Item embeddings

        for num_neurons in hidden_layers:
            mlp_modules.append(nn.Linear(input_dim, num_neurons))
            mlp_modules.append(nn.ReLU())
            mlp_modules.append(nn.Dropout(p=dropout_rate))
            input_dim = num_neurons  # The input dimension for the next layer is the output of the current

        self.mlp_layers = nn.Sequential(*mlp_modules)

        # Output layer
        # A single neuron mapping the last hidden layer to a single prediction score
        self.output_layer = nn.Linear(hidden_layers[-1], 1)
        self.sigmoid = nn.Sigmoid()

        self._init_weights()

    def _init_weights(self) -> None:
        """
        Initializes the weights of the embedding layers and linear layers using
        Xavier uniform initialization to ensure stable gradients during early training.
        """
        nn.init.xavier_uniform_(self.user_embedding.weight)
        nn.init.xavier_uniform_(self.item_embedding.weight)

        for m in self.mlp_layers:
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)
                
        nn.init.xavier_uniform_(self.output_layer.weight)
        nn.init.zeros_(self.output_layer.bias)

    def forward(self, user_indices: torch.Tensor, item_indices: torch.Tensor) -> torch.Tensor:
        """
        Forward pass of the NCF model.

        Args:
            user_indices (torch.Tensor): Tensor containing user IDs (batch_size, ).
            item_indices (torch.Tensor): Tensor containing item IDs (batch_size, ).

        Returns:
            torch.Tensor: Tensor containing probability scores bounded between [0, 1] (batch_size, 1).
        """
        # 1. Extract embeddings
        user_vector = self.user_embedding(user_indices)  # Shape: (batch_size, embedding_dim)
        item_vector = self.item_embedding(item_indices)  # Shape: (batch_size, embedding_dim)

        # 2. Concatenate latent vectors (Implicit Flattening occurs here as vectors are 1D per sample)
        # Shape becomes: (batch_size, embedding_dim * 2)
        concatenated_vector = torch.cat([user_vector, item_vector], dim=-1)

        # 3. Pass through MLP
        mlp_output = self.mlp_layers(concatenated_vector)

        # 4. Final prediction
        prediction = self.output_layer(mlp_output)
        probability_score = self.sigmoid(prediction)

        return probability_score.squeeze()