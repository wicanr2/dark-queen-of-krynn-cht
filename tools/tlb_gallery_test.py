"""組圖的順序、透明、ModeX欄位及拒絕邊界，使用自製圖樣。"""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from tlb_gallery import compose_bank_records


class CompositeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def tile(self, block, color, transparent_corner=False):
        image = Image.new('RGBA', (8, 8), (color, 0, 0, 255))
        if transparent_corner:
            image.putpixel((0, 0), (0, 0, 0, 0))
        name = f'tile-{block}.png'
        image.save(self.out / name)
        (self.out / f'tile-{block}.idx').write_bytes(bytes([color]) * 64)
        return dict(key=f'tile-{block}', block=block, width=8, height=8, x=0, y=0,
                    image=name, sha256=f'fixture-{block}')

    def group(self, block, parts, width=8):
        return dict(key=f'group-{block}', block=block, width=width, height=8,
                    x=0, y=0, sha256=f'fixture-{block}', composite_parts=parts)

    def test_order_and_transparent_background(self):
        group = self.group(3, [dict(block=1, dx=0, dy=0), dict(block=2, dx=0, dy=0)])
        compose_bank_records([self.tile(1, 9), self.tile(2, 4, True), group], self.out)
        result = (self.out / 'group-3.idx').read_bytes()
        self.assertEqual(result[0], 9)
        self.assertEqual(result[1:], bytes([4]) * 63)

    def test_mode_x_column_preserves_logical_offset(self):
        group = self.group(2, [dict(block=1, dx=3, dy=0)], 16)
        compose_bank_records([self.tile(1, 9), group], self.out)
        result = (self.out / 'group-2.idx').read_bytes()
        self.assertEqual(result[:8], bytes([9]) * 8)
        self.assertEqual(result[8:16], bytes([255]) * 8)
        self.assertEqual(group['composite_children'][0]['logical_x'], 3)
        self.assertEqual(group['composite_children'][0]['x'], 0)

    def test_cycle_is_bounded(self):
        a = self.group(1, [dict(block=2, dx=0, dy=0)])
        b = self.group(2, [dict(block=1, dx=0, dy=0)])
        compose_bank_records([a, b], self.out)
        self.assertIn('循環', a['unsupported'])
        self.assertIn('循環', b['unsupported'])

    def test_missing_child_and_bounds_are_rejected(self):
        missing = self.group(2, [dict(block=99, dx=0, dy=0)])
        outside = self.group(3, [dict(block=1, dx=4, dy=0)])
        compose_bank_records([self.tile(1, 9), missing, outside], self.out)
        self.assertIn('不存在', missing['unsupported'])
        self.assertIn('超出', outside['unsupported'])
        self.assertFalse((self.out / 'group-3.png').exists())


if __name__ == '__main__':
    unittest.main()
