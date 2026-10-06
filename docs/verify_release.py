from pathlib import Path
import sys,json,base64,hashlib
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

folder=Path(sys.argv[1] if len(sys.argv)>1 else '.')
expected_fingerprint=sys.argv[2] if len(sys.argv)>2 else '77d3444d0a50a677a3be12c5442de287f370392fd96ccba6fa7d67751347ada4'
cert=x509.load_pem_x509_certificate((folder/'integrity-certificate.pem').read_bytes())
assert cert.fingerprint(hashes.SHA256()).hex()==expected_fingerprint,'Certificate does not match independently retained fingerprint'
payload=(folder/'release-manifest.json').read_bytes()
sig=json.loads((folder/'release-manifest-signature.json').read_text())
cert.public_key().verify(base64.b64decode(sig['signature_base64']),payload,padding.PKCS1v15(),hashes.SHA256())
manifest=json.loads(payload)
for record in manifest['files']:
 path=(folder/record['path']).resolve()
 assert path.is_relative_to(folder.resolve()),'Unsafe manifest path'
 assert path.exists() and path.stat().st_size==record['bytes'],'Missing or size-changed file: '+record['path']
 assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256'],'Changed file: '+record['path']
print('Manifest signature valid; all listed files match; certificate pinned. This verifies integrity, not notarization or identity certification.')
