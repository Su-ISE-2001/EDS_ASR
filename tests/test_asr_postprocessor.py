import unittest

from app.asr.postprocessor import postprocess_text


class AsrPostprocessorTests(unittest.TestCase):
    def test_remove_fillers_and_normalize_terms(self):
        source = "嗯 请帮我 把放大倍数调到一万 曝光时间两百毫秒钟"
        normalized = postprocess_text(source)
        self.assertIn("倍率", normalized)
        self.assertIn("10000", normalized)
        self.assertIn("曝光", normalized)
        self.assertIn("200毫秒", normalized)

    def test_keep_spacing_clean(self):
        source = "  样品A1   倍率  五千   "
        normalized = postprocess_text(source)
        self.assertEqual(normalized, "样品A1 倍率 5000")

    def test_traditional_is_normalized_to_simplified(self):
        source = "樣品A1 放大倍數五千 曝光時間兩百毫秒 幀數二十三"
        normalized = postprocess_text(source)
        self.assertIn("样品A1", normalized)
        self.assertIn("倍率5000", normalized.replace(" ", ""))
        self.assertIn("曝光200毫秒", normalized.replace(" ", ""))
        self.assertIn("张数23", normalized.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
