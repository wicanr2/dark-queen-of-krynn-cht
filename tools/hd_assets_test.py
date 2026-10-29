"""防止幾乎透明的生成雜點擠縮戰棋構圖，或將背景RGB延展成實心色條。"""
import unittest

from PIL import Image
from hd_assets import compile_sprite


class SpriteMaskRegression(unittest.TestCase):
    def test_invisible_noise_does_not_change_composition(self):
        original = Image.new('RGBA', (24, 24))
        original.paste((20, 20, 20, 255), (3, 1, 21, 24))
        master = Image.new('RGBA', (160, 160))
        master.paste((180, 120, 30, 255), (70, 25, 95, 140))
        clean = compile_sprite(original, master)
        master.putpixel((0, 0), (240, 240, 240, 1))
        master.putpixel((159, 159), (250, 250, 250, 31))
        self.assertEqual(compile_sprite(original, master).tobytes(), clean.tobytes())
        self.assertEqual(clean.getchannel('A').tobytes(),
                         original.getchannel('A').resize((72, 72), Image.Resampling.NEAREST).tobytes())

    def test_missing_art_uses_outline_without_color_extrusion(self):
        original = Image.new('RGBA', (8, 8), (0, 0, 0, 255))
        master = Image.new('RGBA', (24, 24), (180, 180, 180, 255))
        master.paste((255, 0, 255, 0), (5, 5, 19, 19))
        result = compile_sprite(original, master)
        self.assertEqual(result.getpixel((12, 12)), (0, 0, 0, 255))
        self.assertEqual(result.getpixel((1, 1)), (180, 180, 180, 255))


if __name__ == '__main__':
    unittest.main()
