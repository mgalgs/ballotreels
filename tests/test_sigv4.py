import unittest

from ballotreels import sigv4


class SigningKeyTest(unittest.TestCase):
    def test_signing_key_iam_example(self):
        key = sigv4.signing_key(
            "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", "20150830",
            "us-east-1", "iam")
        self.assertEqual(
            key.hex(),
            "c4afb1cc5771d871763a393e44b703571b55cc28424d1a5e86da6ed3c154a4b9")


class GetVanillaTest(unittest.TestCase):
    def test_get_vanilla(self):
        empty_hash = sigv4.sha256_hex(b"")
        headers = {"Host": "example.amazonaws.com",
                  "X-Amz-Date": "20150830T123600Z"}
        signature = sigv4.sign(
            "GET", "/", "", headers, ["Host", "X-Amz-Date"], empty_hash,
            "20150830T123600Z", "us-east-1", "service",
            "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY")
        self.assertEqual(
            signature,
            "5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31")


class S3GetObjectExampleTest(unittest.TestCase):
    def test_s3_get_object_example(self):
        empty_hash = sigv4.sha256_hex(b"")
        headers = {"Host": "examplebucket.s3.amazonaws.com",
                  "Range": "bytes=0-9",
                  "x-amz-content-sha256": empty_hash,
                  "x-amz-date": "20130524T000000Z"}
        signature = sigv4.sign(
            "GET", "/test.txt", "", headers,
            ["Host", "Range", "x-amz-content-sha256", "x-amz-date"],
            empty_hash, "20130524T000000Z", "us-east-1", "s3",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        self.assertEqual(
            signature,
            "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")


class CanonicalUriTest(unittest.TestCase):
    def test_no_double_encoding(self):
        # A path segment is encoded once; '/' stays a separator.
        self.assertEqual(sigv4.canonical_uri("/a b/c"), "/a%20b/c")
        self.assertEqual(sigv4.canonical_uri("/already%20encoded"),
                         "/already%2520encoded")


if __name__ == "__main__":
    unittest.main()
