import sys
import os
import unittest

# Add project root to path
sys.path.append(os.getcwd())

from app.core.structure_propagator import StructurePropagator

class TestStructurePropagator(unittest.TestCase):
    def setUp(self):
        self.propagator = StructurePropagator()
        
        # Simulate OCR Data (Raw Words)
        # Represents a list:
        # 01. Item A
        # 02. Item B
        # 03. Item C
        self.raw_words = [
            # 01. Item A
            {'rect': [100, 100, 120, 120], 'text': '01.'},
            {'rect': [130, 100, 200, 120], 'text': 'Item'},
            {'rect': [210, 100, 230, 120], 'text': 'A'},
            
            # 02. Item B (Offset +50 Y)
            {'rect': [100, 150, 120, 170], 'text': '02.'},
            {'rect': [130, 150, 200, 170], 'text': 'Item'},
            {'rect': [210, 150, 230, 170], 'text': 'B'},
            
            # 03. Item C (Offset +100 Y)
            {'rect': [100, 200, 120, 220], 'text': '03.'},
            {'rect': [130, 200, 200, 220], 'text': 'Item'},
            {'rect': [210, 200, 230, 220], 'text': 'C'},
            
            # Noise
            {'rect': [500, 500, 600, 600], 'text': 'Footer'},
        ]
        
        self.page_size = (1000, 1000)

    def test_propagate_regex_header(self):
        """Test propagating a numbered list (Regex header detection)"""
        # Template covers "01. Item A"
        template = {
            'rect': [90, 90, 240, 130], # Covers 01. Item A loosely
            'text': '01. Item A'
        }
        
        results = self.propagator.propagate(template, self.raw_words, self.page_size)
        
        print(f"Detected {len(results)} regions.")
        for r in results:
            print(f" - {r['rect']} Anchor: {r.get('anchor_word')}")
            
        # Expect 3 regions (01, 02, 03)
        # Note: Logic defines new regions based on Anchor position
        self.assertGreaterEqual(len(results), 3)
        
        # Verify approximate Y coordinates
        y_coords = sorted([r['rect'][1] for r in results])
        # 01 starts at ~90 (template). 
        # 02 starts at ~140 (based on anchor at 150 minus offset).
        # Anchor logic: proj_rect = anchor.x - margin...
        # Let's check logic:
        # In code: proj_rect = word[rect][0] - 10 ...
        # Word '01.' is [100, 100]
        # Proj: 90, 90 ... matches template [90,90]
        
        # Word '02.' is [100, 150]
        # Proj: 90, 140 ...
        
        self.assertAlmostEqual(y_coords[0], 90, delta=10)
        self.assertAlmostEqual(y_coords[1], 140, delta=10)
        self.assertAlmostEqual(y_coords[2], 190, delta=10)

if __name__ == '__main__':
    unittest.main()
