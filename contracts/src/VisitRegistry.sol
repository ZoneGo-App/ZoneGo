// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract VisitRegistry {
    // indexed: enables efficient filtering from the subgraph.
    event VisitRecorded(
        uint256 indexed campaignId,
        address indexed visitor,
        bytes32 nullifierHash,
        uint64 timestamp,
        bytes32 sigHash
    );

    event RewardPaid(uint256 indexed campaignId, address indexed visitor, uint256 amount);

    // Payload signed by the merchant via EIP-712, embedded in the QR code.
    struct VisitSig {
        uint256 campaignId;
        uint256 nonce;
        uint64 expiry;
        bytes32 geohash;
    }

    // Hash of the VisitSig struct shape. Constant — computed once at compile
    // time, never changes. Used to reconstruct the signed message.
    bytes32 public constant VISIT_TYPEHASH = keccak256(
        "VisitSig(uint256 campaignId,uint256 nonce,uint64 expiry,bytes32 geohash)"
    );

    // TODO(day 3): verify EIP-712 signature, nullifier, daily cap.
    function claim(VisitSig calldata sig, bytes calldata signature, bytes calldata worldProof) external {
        revert("not implemented");
    }
}