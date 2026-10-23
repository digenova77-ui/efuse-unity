# Redundant pinning

Pinata is one pinner. To survive a single pinner failure:

1. Pin the snapshot (`node scripts/pin-pinata.mjs --pin` or the workflow). Note the CID.
2. On any other IPFS node:
   ```
   ipfs pin add <CID>
   ```
3. Optional: add the CID to a second pinning service (web3.storage, nft.storage, or a self-hosted node).
4. Update IPNS to the CID only after at least two pinners report the pin.

The pure snapshot is content-addressed. Any node that pins the same CID is a redundant pinner.
