"""Small trainable U-Net suitable as a baseline; requires PyTorch only at use time."""
from __future__ import annotations

try:
    import torch
    from torch import nn
except ImportError:  # Keeps non-ML modules importable before optional install.
    torch = None
    nn = object  # type: ignore[assignment]


if torch is not None:
    class ConvBlock(nn.Module):
        def __init__(self, in_channels: int, out_channels: int) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 3, padding=1), nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True),
                nn.Conv2d(out_channels, out_channels, 3, padding=1), nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True),
            )

        def forward(self, x):  # type: ignore[no-untyped-def]
            return self.net(x)


    class TinyUNet(nn.Module):
        """Two-level U-Net baseline for VV/VH Sentinel-1 tiles."""
        def __init__(self, in_channels: int = 2, base_channels: int = 32) -> None:
            super().__init__()
            self.enc1 = ConvBlock(in_channels, base_channels)
            self.pool = nn.MaxPool2d(2)
            self.enc2 = ConvBlock(base_channels, base_channels * 2)
            self.bottleneck = ConvBlock(base_channels * 2, base_channels * 4)
            self.up2 = nn.ConvTranspose2d(base_channels * 4, base_channels * 2, 2, stride=2)
            self.dec2 = ConvBlock(base_channels * 4, base_channels * 2)
            self.up1 = nn.ConvTranspose2d(base_channels * 2, base_channels, 2, stride=2)
            self.dec1 = ConvBlock(base_channels * 2, base_channels)
            self.head = nn.Conv2d(base_channels, 1, 1)

        def forward(self, x):  # type: ignore[no-untyped-def]
            e1 = self.enc1(x)
            e2 = self.enc2(self.pool(e1))
            b = self.bottleneck(self.pool(e2))
            d2 = self.dec2(torch.cat((self.up2(b), e2), dim=1))
            d1 = self.dec1(torch.cat((self.up1(d2), e1), dim=1))
            return self.head(d1)
else:
    class TinyUNet:  # type: ignore[no-redef]
        def __init__(self, *_: object, **__: object) -> None:
            raise RuntimeError("Install optional ML dependencies: pip install -e '.[ml]'")
