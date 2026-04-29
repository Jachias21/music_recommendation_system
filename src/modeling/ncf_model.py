import torch
import torch.nn as nn
from typing import List

class NeuralCollaborativeFiltering(nn.Module):
    def __init__(
        self, 
        num_users: int, 
        num_items: int, 
        item_features_dim: int = 0,
        embedding_dim: int = 64, 
        hidden_layers: List[int] = [128, 64, 32], 
        dropout_rate: float = 0.2
    ) -> None:
        super(NeuralCollaborativeFiltering, self).__init__()

        self.user_embedding = nn.Embedding(num_embeddings=num_users, embedding_dim=embedding_dim)
        self.item_embedding = nn.Embedding(num_embeddings=num_items, embedding_dim=embedding_dim)

        #User Embedding + Item Embedding + Features Reales
        input_dim = (embedding_dim * 2) + item_features_dim 
        
        mlp_modules = []
        for num_neurons in hidden_layers:
            mlp_modules.append(nn.Linear(input_dim, num_neurons))
            mlp_modules.append(nn.ReLU())
            mlp_modules.append(nn.Dropout(p=dropout_rate))
            input_dim = num_neurons  

        self.mlp_layers = nn.Sequential(*mlp_modules)
        self.output_layer = nn.Linear(hidden_layers[-1], 1)
        self.sigmoid = nn.Sigmoid()

        self._init_weights()

    def _init_weights(self) -> None:
        nn.init.xavier_uniform_(self.user_embedding.weight)
        nn.init.xavier_uniform_(self.item_embedding.weight)
        for m in self.mlp_layers:
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)
        nn.init.xavier_uniform_(self.output_layer.weight)
        nn.init.zeros_(self.output_layer.bias)

    def forward(self, user_indices: torch.Tensor, item_indices: torch.Tensor, item_features: torch.Tensor = None) -> torch.Tensor:
        user_vector = self.user_embedding(user_indices)
        item_vector = self.item_embedding(item_indices)

        # Si pasamos features, las añadimos al vector de entrada
        if item_features is not None:
            concatenated_vector = torch.cat([user_vector, item_vector, item_features], dim=-1)
        else:
            concatenated_vector = torch.cat([user_vector, item_vector], dim=-1)

        mlp_output = self.mlp_layers(concatenated_vector)
        prediction = self.output_layer(mlp_output)
        return self.sigmoid(prediction).squeeze()