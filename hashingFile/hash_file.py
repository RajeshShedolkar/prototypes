import hashlib

def generate_file_hash(file_path):
    sha256 = hashlib.sha256()

    # file binary mode open
    with open(file_path, "rb") as f:
        # large files chunk-wise read
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


if __name__ == "__main__":
    pdf_path = "sample2.pdf"
    file_hash = generate_file_hash(pdf_path)
    print("SHA-256 Hash:", file_hash)
