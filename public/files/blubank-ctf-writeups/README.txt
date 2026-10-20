BluBank CTF challenge files
===========================

The artifacts from the writeup "Writeups for some of the BluBank CTF challenges".
The CTF has ended and these are published for anyone who wants to work the
challenges themselves.

matcha/
  matcha           stripped x86-64 PIE binary, the challenge itself
  flag.enc         five lines of 16 hex characters, the ciphertext
  solve_matcha.py  solver; reads a flag.enc and prints the flag

    cd matcha
    chmod +x matcha
    cp flag.enc flag.enc.orig
    python3 solve_matcha.py flag.enc
    printf 'BDD{03d5a29801f0f97e40d84e83eb53562d}' > flag.txt
    ./matcha && diff flag.enc flag.enc.orig && echo IDENTICAL

greenchain/
  GreenChain.apk        the challenge APK, unmodified (9.6 MB)
  greenchain_solve.py   solver; takes the directory holding the three assets

    cd greenchain
    unzip -o GreenChain.apk 'assets/*' -d gc
    python3 greenchain_solve.py gc/assets

softfocus/
  proof_bundle.json    the published proof bundle (first instance)
  prover.py            the prover that produced it
  verifier.py          the verifier that accepts it
  softfocus_solve.py   recovers the credential, then the attachment
  reproduce_flaw.py    runs prover.py on a fresh credential and breaks it again

    cd softfocus
    python3 verifier.py proof_bundle.json
    python3 softfocus_solve.py proof_bundle.json
    python3 reproduce_flaw.py proof_bundle.json

softfocus-n3/
  proof_bundle.json    the second instance's bundle; same prover and verifier

    cd softfocus
    python3 softfocus_solve.py ../softfocus-n3/proof_bundle.json

Requirements: python3, and the `cryptography` package for greenchain_solve.py.
openssl is used for the independent decryption check in the writeup.

The flags in these files are the recorded ones: the flags are stale and the CTF
is over.
