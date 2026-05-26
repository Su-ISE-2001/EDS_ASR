import unittest

from app.config.settings import CaptureDefaultSettings
from app.domain.params import CaptureParams, ParamValidationError
from app.nlu.parser import IntentParamParser


class ParserAndParamsTests(unittest.TestCase):
    def test_capture_params_validate_success(self):
        params = CaptureParams(
            sample_id="sampleA",
            magnification=10000,
            exposure_ms=200,
            frame_count=3,
            save_dir="data/output",
        )
        params.validate()

    def test_capture_params_validate_fail(self):
        params = CaptureParams(
            sample_id="",
            magnification=5,
            exposure_ms=0,
            frame_count=0,
            save_dir="",
        )
        with self.assertRaises(ParamValidationError):
            params.validate()

    def test_parser_extract_fields(self):
        parser = IntentParamParser(
            CaptureDefaultSettings(
                sample_id="default",
                magnification=5000,
                exposure_ms=100,
                frame_count=1,
                save_dir="data/output",
            )
        )
        text = "样品A12 倍率15000 曝光300ms 拍5张 保存到D:\\\\capture"
        parsed = parser.parse(text)
        self.assertEqual(parsed.params.sample_id, "A12")
        self.assertEqual(parsed.params.magnification, 15000)
        self.assertEqual(parsed.params.exposure_ms, 300)
        self.assertEqual(parsed.params.frame_count, 5)


if __name__ == "__main__":
    unittest.main()
