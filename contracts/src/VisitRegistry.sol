// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {CampaignVault} from "./CampaignVault.sol";

contract VisitRegistry is EIP712 {
    CampaignVault public immutable VAULT;

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
    }

    bytes32 public constant VISIT_TYPEHASH = keccak256(
        "VisitSig(uint256 campaignId,uint256 nonce,uint64 expiry,bytes32 geohash)"
    );

    mapping(address => mapping(uint256 => bool)) public usedNonce;
    mapping(bytes32 => uint8) public visitsThisWeek;
    mapping(bytes32 => uint256) public dailySpent;

    error SignatureExpired();
    error NonceAlreadyUsed();
    error BadSig();
    error CampaignNotFound();
    error DailyCapExceeded();

    constructor(address vault) EIP712("ZoneGo", "1") {
        VAULT = CampaignVault(vault);
    }

    function claim(VisitSig calldata sig, address visitor, bytes calldata signature, bytes32 nullifierHash)
        external
    {
        if (block.timestamp > sig.expiry) revert SignatureExpired();

        (address merchant, uint256 rewardPerVisit, uint256 dailyCap,,,) = VAULT.campaigns(sig.campaignId);
        if (merchant == address(0)) revert CampaignNotFound();
        if (usedNonce[merchant][sig.nonce]) revert NonceAlreadyUsed();

        bytes32 structHash = keccak256(
            abi.encode(VISIT_TYPEHASH, sig.campaignId, sig.nonce, sig.expiry, sig.geohash)
        );
        address recovered = ECDSA.recover(_hashTypedDataV4(structHash), signature);
        if (recovered != merchant) revert BadSig();

        usedNonce[merchant][sig.nonce] = true;

        // TODO(day 5): verify nullifierHash against World ID router — trusted
        // as given for now.

        bytes32 weekKey = keccak256(abi.encode(sig.campaignId, nullifierHash, block.timestamp / 1 weeks));
        uint8 count = visitsThisWeek[weekKey];
        visitsThisWeek[weekKey] = count + 1;

        uint256 percent = count == 0 ? 100 : count == 1 ? 50 : count == 2 ? 25 : 0;
        uint256 amount = (rewardPerVisit * percent) / 100;

        if (amount > 0) {
            bytes32 dayKey = keccak256(abi.encode(sig.campaignId, block.timestamp / 1 days));
            uint256 spentToday = dailySpent[dayKey] + amount;
            if (spentToday > dailyCap) revert DailyCapExceeded();
            dailySpent[dayKey] = spentToday;

            VAULT.payReward(sig.campaignId, visitor, amount);
            emit RewardPaid(sig.campaignId, visitor, amount);
        }

        emit VisitRecorded(sig.campaignId, visitor, nullifierHash, uint64(block.timestamp), keccak256(signature));
    }
}