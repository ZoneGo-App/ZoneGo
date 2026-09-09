// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {CampaignVault} from "./CampaignVault.sol";

contract VisitRegistry is EIP712 {
    CampaignVault public immutable VAULT;
    address public immutable TRUSTED_ATTESTER;

    event VisitRecorded(
        uint256 indexed campaignId,
        address indexed visitor,
        bytes32 nullifierHash,
        uint64 timestamp,
        bytes32 sigHash
    );
    event RewardPaid(uint256 indexed campaignId, address indexed visitor, uint256 amount);

    struct VisitSig {
        uint256 campaignId;
        uint256 nonce;
        uint64 expiry;
        bytes32 geohash;
        address visitor;
    }

    struct WorldAttestation {
        address visitor;
        bytes32 nullifierHash;
        uint64 expiry;
    }

    bytes32 public constant VISIT_TYPEHASH = keccak256(
        "VisitSig(uint256 campaignId,uint256 nonce,uint64 expiry,bytes32 geohash,address visitor)"
    );

    bytes32 public constant ATTESTATION_TYPEHASH = keccak256(
        "WorldAttestation(address visitor,bytes32 nullifierHash,uint64 expiry)"
    );

    mapping(address => mapping(uint256 => bool)) public usedNonce;
    mapping(bytes32 => uint8) public visitsThisWeek;
    mapping(bytes32 => uint256) public visitsToday;
    mapping(bytes32 => address) public nullifierBoundTo;
    mapping(bytes32 => bool) public usedAttestation;

    error AttestationAlreadyUsed();
    error SignatureExpired();
    error NonceAlreadyUsed();
    error BadSig();
    error CampaignNotFound();
    error DailyCapExceeded();
    error GeohashMismatch();
    error AttestationExpired();
    error BadAttestationSig();
    error AttestationVisitorMismatch();
    error NullifierBoundToOtherVisitor();

    constructor(address vault, address attester) EIP712("ZoneGo", "1") {
        VAULT = CampaignVault(vault);
        TRUSTED_ATTESTER = attester;
    }

    function claim(
        VisitSig calldata sig,
        bytes calldata signature,
        WorldAttestation calldata attestation,
        bytes calldata attestationSignature
    ) external {
        if (block.timestamp > sig.expiry) revert SignatureExpired();

        (address merchant, uint256 rewardPerVisit, uint256 dailyCap, bytes32 campaignGeohash,,) =
            VAULT.campaigns(sig.campaignId);
        if (merchant == address(0)) revert CampaignNotFound();
        if (sig.geohash != campaignGeohash) revert GeohashMismatch();
        if (usedNonce[merchant][sig.nonce]) revert NonceAlreadyUsed();

        bytes32 structHash = keccak256(
            abi.encode(VISIT_TYPEHASH, sig.campaignId, sig.nonce, sig.expiry, sig.geohash, sig.visitor)
        );
        address recovered = ECDSA.recover(_hashTypedDataV4(structHash), signature);
        if (recovered != merchant) revert BadSig();

        if (block.timestamp > attestation.expiry) revert AttestationExpired();
        if (attestation.visitor != sig.visitor) revert AttestationVisitorMismatch();

        bytes32 attestationHash = keccak256(
            abi.encode(ATTESTATION_TYPEHASH, attestation.visitor, attestation.nullifierHash, attestation.expiry)
        );
        address attester = ECDSA.recover(_hashTypedDataV4(attestationHash), attestationSignature);
        if (attester != TRUSTED_ATTESTER) revert BadAttestationSig();

        bytes32 attestationSigHash = keccak256(attestationSignature);
        if (usedAttestation[attestationSigHash]) revert AttestationAlreadyUsed();
        usedAttestation[attestationSigHash] = true;

        bytes32 nullifierHash = attestation.nullifierHash;

        address boundTo = nullifierBoundTo[nullifierHash];
        if (boundTo == address(0)) {
            nullifierBoundTo[nullifierHash] = sig.visitor;
        } else if (boundTo != sig.visitor) {
            revert NullifierBoundToOtherVisitor();
        }

        bytes32 dayKey = keccak256(abi.encode(sig.campaignId, block.timestamp / 1 days));
        uint256 countToday = visitsToday[dayKey] + 1;
        if (countToday > dailyCap) revert DailyCapExceeded();
        visitsToday[dayKey] = countToday;

        usedNonce[merchant][sig.nonce] = true;

        bytes32 weekKey = keccak256(abi.encode(sig.campaignId, nullifierHash, block.timestamp / 1 weeks));
        uint8 count = visitsThisWeek[weekKey];
        visitsThisWeek[weekKey] = count + 1;

        uint256 percent = count == 0 ? 100 : count == 1 ? 50 : count == 2 ? 25 : 0;
        uint256 amount = (rewardPerVisit * percent) / 100;

        if (amount > 0) {
            VAULT.payReward(sig.campaignId, sig.visitor, amount);
            emit RewardPaid(sig.campaignId, sig.visitor, amount);
        }

        emit VisitRecorded(sig.campaignId, sig.visitor, nullifierHash, uint64(block.timestamp), keccak256(signature));
    }
}