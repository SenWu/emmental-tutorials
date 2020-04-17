import sys

import torch
import torch.nn as nn
import torch.nn.functional as F


def deep_iter(x):
    if isinstance(x, list) or isinstance(x, tuple):
        for u in x:
            for v in deep_iter(u):
                yield v
    else:
        yield x


class CNN(nn.Module):
    def __init__(self, n_in, widths=[3, 4, 5], filters=100):
        super(CNN, self).__init__()
        Ci = 1
        Co = filters
        h = n_in
        self.convs1 = nn.ModuleList([nn.Conv2d(Ci, Co, (w, h)) for w in widths])

    def forward(self, x):
        # x is (batch, len, d)
        x = x.unsqueeze(1)  # (batch, Ci, len, d)
        x = [
            F.relu(conv(x)).squeeze(3) for conv in self.convs1
        ]  # [(batch, Co, len), ...]
        x = [F.max_pool1d(i, i.size(2)).squeeze(2) for i in x]  # [(N,Co), ...]
        x = torch.cat(x, 1)
        return x


class LSTM(nn.Module):
    def __init__(self, n_d, dim, depth, dropout):
        super(LSTM, self).__init__()
        self.LSTM = nn.LSTM(
            input_size=n_d,
            hidden_size=dim,
            num_layers=depth,
            batch_first=True,
            dropout=dropout,
        )

    def forward(self, x):
        output, hidden = self.LSTM.forward(x)
        return output[:, -1, :]


class EmbeddingLayer(nn.Module):
    def __init__(
        self,
        n_d,
        words,
        embs=None,
        fix_emb=True,
        oov="~#OoV#~",
        pad="~#PaD#~",
        normalize=True,
    ):
        super(EmbeddingLayer, self).__init__()
        word2id = {}
        word2id[pad] = len(word2id)
        word2id[oov] = len(word2id)

        if embs is not None:
            embwords, embvecs = embs
            for word in embwords:
                assert word not in word2id, "Duplicate words in pre-trained embeddings"
                word2id[word] = len(word2id)

            sys.stdout.write(
                "{} pre-trained word embeddings loaded.\n".format(len(word2id))
            )
            if n_d != len(embvecs[0]):
                sys.stdout.write(
                    f"[WARNING] n_d ({n_d}) != word vector size ({len(embvecs[0])})."
                    f"Use {len(embvecs[0])} for embeddings."
                )
                n_d = len(embvecs[0])

        for w in deep_iter(words):
            if w not in word2id:
                word2id[w] = len(word2id)

        self.word2id = word2id
        self.n_V, self.n_d = len(word2id), n_d
        self.oovid = word2id[oov]
        self.padid = word2id[pad]
        self.embedding = nn.Embedding(self.n_V, n_d)
        self.embedding.weight.data.uniform_(-0.25, 0.25)

        if embs is not None:
            weight = self.embedding.weight
            weight.data[2: len(embwords) + 2].copy_(torch.from_numpy(embvecs))
            sys.stdout.write("embedding shape: {}\n".format(weight.size()))

        if normalize:
            weight = self.embedding.weight
            norms = weight.data.norm(2, 1)
            if norms.dim() == 1:
                norms = norms.unsqueeze(1)
            weight.data.div_(norms.expand_as(weight.data))

        if fix_emb:
            self.embedding.weight.requires_grad = False

    def forward(self, input):
        return self.embedding(input)


class Average(nn.Module):
    def __init__(self):
        super(Average, self).__init__()

    def forward(self, x):
        return x.sum(dim=1) / x.size()[1]
