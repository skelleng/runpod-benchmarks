import torch
a = torch.randn((4096, 4096), device='cuda')
b = torch.randn((4096, 4096), device='cuda')
for _ in range(10):
    torch.mm(a, b)
