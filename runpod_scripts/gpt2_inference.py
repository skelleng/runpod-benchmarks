from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch
tok = GPT2Tokenizer.from_pretrained('gpt2')
model = GPT2LMHeadModel.from_pretrained('gpt2').cuda()
inputs = tok('Hello world', return_tensors='pt').to('cuda')
with torch.no_grad():
    model.generate(**inputs, max_length=50)
