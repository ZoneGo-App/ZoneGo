// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {VisitRegistry} from "../src/VisitRegistry.sol";
import {CampaignVault} from "../src/CampaignVault.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockUSDC is ERC20 {
    constructor() ERC20("Mock USDC", "USDC") {
        _mint(msg.sender, 1_000_000e6);
    }
}

contract VisitRegistryTest is Test {
    CampaignVault vault;
    VisitRegistry registry;
    MockUSDC usdc;

    uint256 merchantKey = 0xA11CE;
    uint256 attesterKey = 0xB0B;
    address merchant;
    address attester;
    address visitor = address(0x2);
    uint256 campaignId;

    function setUp() public {
        merchant = vm.addr(merchantKey);
        attester = vm.addr(attesterKey);
        usdc = new MockUSDC();
        vault = new CampaignVault(address(usdc));
        registry = new VisitRegistry(address(vault), attester);
        vault.setVisitRegistry(address(registry));

        vm.prank(merchant);
        campaignId = vault.createCampaign(10e6, 1000e6, bytes32(0), 1000);

        usdc.transfer(merchant, 500e6);
        vm.prank(merchant);
        usdc.approve(address(vault), 500e6);
        vm.prank(merchant);
        vault.fund(campaignId, 500e6);
    }

    function _domainSeparator() internal view returns (bytes32) {
        return keccak256(
            abi.encode(
                keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
                keccak256("ZoneGo"),
                keccak256("1"),
                block.chainid,
                address(registry)
            )
        );
    }

    function _sign(VisitRegistry.VisitSig memory sig, uint256 signerKey) internal view returns (bytes memory) {
        bytes32 structHash = keccak256(
            abi.encode(
                registry.VISIT_TYPEHASH(), sig.campaignId, sig.nonce, sig.expiry, sig.geohash, sig.visitor
            )
        );
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", _domainSeparator(), structHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerKey, digest);
        return abi.encodePacked(r, s, v);
    }

    function _signAttestation(VisitRegistry.WorldAttestation memory att, uint256 signerKey)
        internal
        view
        returns (bytes memory)
    {
        bytes32 structHash = keccak256(
            abi.encode(registry.ATTESTATION_TYPEHASH(), att.visitor, att.nullifierHash, att.expiry)
        );
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", _domainSeparator(), structHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerKey, digest);
        return abi.encodePacked(r, s, v);
    }

    function test_ReusedNonceReverts() public {
        VisitRegistry.VisitSig memory sig = VisitRegistry.VisitSig({
            campaignId: campaignId,
            nonce: 1,
            expiry: uint64(block.timestamp + 1 hours),
            geohash: bytes32(0),
            visitor: visitor
        });
        bytes memory signature = _sign(sig, merchantKey);

        VisitRegistry.WorldAttestation memory attestation = VisitRegistry.WorldAttestation({
            visitor: visitor,
            nullifierHash: keccak256("human-1"),
            expiry: uint64(block.timestamp + 2 minutes)
        });
        bytes memory attestationSignature = _signAttestation(attestation, attesterKey);

        registry.claim(sig, signature, attestation, attestationSignature);

        vm.expectRevert(VisitRegistry.NonceAlreadyUsed.selector);
        registry.claim(sig, signature, attestation, attestationSignature);
    }

    function test_DecreasingCurvePaysCorrectAmounts() public {
        bytes32 nullifier = keccak256("human-1");
        uint256[4] memory expectedAmounts = [uint256(10e6), 5e6, 2.5e6, 0];

        for (uint256 i = 0; i < 4; i++) {
            VisitRegistry.VisitSig memory sig = VisitRegistry.VisitSig({
                campaignId: campaignId,
                nonce: i + 1,
                expiry: uint64(block.timestamp + 1 hours),
                geohash: bytes32(0),
                visitor: visitor
            });
            bytes memory signature = _sign(sig, merchantKey);

            VisitRegistry.WorldAttestation memory attestation = VisitRegistry.WorldAttestation({
                visitor: visitor,
                nullifierHash: nullifier,
                expiry: uint64(block.timestamp + 2 minutes + i)
            });
            bytes memory attestationSignature = _signAttestation(attestation, attesterKey);

            uint256 balanceBefore = usdc.balanceOf(visitor);
            registry.claim(sig, signature, attestation, attestationSignature);
            uint256 paid = usdc.balanceOf(visitor) - balanceBefore;
            assertEq(paid, expectedAmounts[i], "wrong amount for visit");
        }
    }

    function test_ExpiredSignatureReverts() public {
        VisitRegistry.VisitSig memory sig = VisitRegistry.VisitSig({
            campaignId: campaignId,
            nonce: 1,
            expiry: uint64(block.timestamp == 0 ? 0 : block.timestamp - 1),
            geohash: bytes32(0),
            visitor: visitor
        });
        bytes memory signature = _sign(sig, merchantKey);

        VisitRegistry.WorldAttestation memory attestation = VisitRegistry.WorldAttestation({
            visitor: visitor,
            nullifierHash: keccak256("human-1"),
            expiry: uint64(block.timestamp + 2 minutes)
        });
        bytes memory attestationSignature = _signAttestation(attestation, attesterKey);

        vm.expectRevert(VisitRegistry.SignatureExpired.selector);
        registry.claim(sig, signature, attestation, attestationSignature);
    }

    function test_WrongSignerReverts() public {
        VisitRegistry.VisitSig memory sig = VisitRegistry.VisitSig({
            campaignId: campaignId,
            nonce: 1,
            expiry: uint64(block.timestamp + 1 hours),
            geohash: bytes32(0),
            visitor: visitor
        });
        uint256 wrongKey = 0xBAD;
        bytes memory badSignature = _sign(sig, wrongKey);

        VisitRegistry.WorldAttestation memory attestation = VisitRegistry.WorldAttestation({
            visitor: visitor,
            nullifierHash: keccak256("human-1"),
            expiry: uint64(block.timestamp + 2 minutes)
        });
        bytes memory attestationSignature = _signAttestation(attestation, attesterKey);

        vm.expectRevert(VisitRegistry.BadSig.selector);
        registry.claim(sig, badSignature, attestation, attestationSignature);
    }

    function test_ReusedAttestationReverts() public {
        VisitRegistry.VisitSig memory sig1 = VisitRegistry.VisitSig({
            campaignId: campaignId,
            nonce: 1,
            expiry: uint64(block.timestamp + 1 hours),
            geohash: bytes32(0),
            visitor: visitor
        });
        bytes memory signature1 = _sign(sig1, merchantKey);

        VisitRegistry.WorldAttestation memory attestation = VisitRegistry.WorldAttestation({
            visitor: visitor,
            nullifierHash: keccak256("human-1"),
            expiry: uint64(block.timestamp + 2 minutes)
        });
        bytes memory attestationSignature = _signAttestation(attestation, attesterKey);

        registry.claim(sig1, signature1, attestation, attestationSignature);

        VisitRegistry.VisitSig memory sig2 = VisitRegistry.VisitSig({
            campaignId: campaignId,
            nonce: 2,
            expiry: uint64(block.timestamp + 1 hours),
            geohash: bytes32(0),
            visitor: visitor
        });
        bytes memory signature2 = _sign(sig2, merchantKey);

        vm.expectRevert(VisitRegistry.AttestationAlreadyUsed.selector);
        registry.claim(sig2, signature2, attestation, attestationSignature);
    }

    function test_NullifierBoundToOtherVisitorReverts() public {
        bytes32 nullifier = keccak256("human-1");

        VisitRegistry.VisitSig memory sig1 = VisitRegistry.VisitSig({
            campaignId: campaignId,
            nonce: 1,
            expiry: uint64(block.timestamp + 1 hours),
            geohash: bytes32(0),
            visitor: visitor
        });
        bytes memory signature1 = _sign(sig1, merchantKey);

        VisitRegistry.WorldAttestation memory attestation1 = VisitRegistry.WorldAttestation({
            visitor: visitor,
            nullifierHash: nullifier,
            expiry: uint64(block.timestamp + 2 minutes)
        });
        bytes memory attestationSignature1 = _signAttestation(attestation1, attesterKey);

        registry.claim(sig1, signature1, attestation1, attestationSignature1);

        address otherVisitor = address(0x3);
        VisitRegistry.VisitSig memory sig2 = VisitRegistry.VisitSig({
            campaignId: campaignId,
            nonce: 2,
            expiry: uint64(block.timestamp + 1 hours),
            geohash: bytes32(0),
            visitor: otherVisitor
        });
        bytes memory signature2 = _sign(sig2, merchantKey);

        VisitRegistry.WorldAttestation memory attestation2 = VisitRegistry.WorldAttestation({
            visitor: otherVisitor,
            nullifierHash: nullifier,
            expiry: uint64(block.timestamp + 3 minutes)
        });
        bytes memory attestationSignature2 = _signAttestation(attestation2, attesterKey);

        vm.expectRevert(VisitRegistry.NullifierBoundToOtherVisitor.selector);
        registry.claim(sig2, signature2, attestation2, attestationSignature2);
    }

    function test_DailyCapExceededReverts() public {
        usdc.transfer(merchant, 100e6);

        vm.startPrank(merchant);
        uint256 smallCapCampaign = vault.createCampaign(10e6, 2, bytes32(0), 1000);
        usdc.approve(address(vault), 100e6);
        vault.fund(smallCapCampaign, 100e6);
        vm.stopPrank();

        bytes32 nullifier = keccak256("human-daily-cap");

        for (uint256 i = 0; i < 2; i++) {
            VisitRegistry.VisitSig memory sig = VisitRegistry.VisitSig({
                campaignId: smallCapCampaign,
                nonce: 100 + i,
                expiry: uint64(block.timestamp + 1 hours),
                geohash: bytes32(0),
                visitor: visitor
            });
            bytes memory signature = _sign(sig, merchantKey);

            VisitRegistry.WorldAttestation memory attestation = VisitRegistry.WorldAttestation({
                visitor: visitor,
                nullifierHash: nullifier,
                expiry: uint64(block.timestamp + 2 minutes + i)
            });
            bytes memory attestationSignature = _signAttestation(attestation, attesterKey);

            registry.claim(sig, signature, attestation, attestationSignature);
        }

        VisitRegistry.VisitSig memory sigThird = VisitRegistry.VisitSig({
            campaignId: smallCapCampaign,
            nonce: 103,
            expiry: uint64(block.timestamp + 1 hours),
            geohash: bytes32(0),
            visitor: visitor
        });
        bytes memory signatureThird = _sign(sigThird, merchantKey);

        VisitRegistry.WorldAttestation memory attestationThird = VisitRegistry.WorldAttestation({
            visitor: visitor,
            nullifierHash: nullifier,
            expiry: uint64(block.timestamp + 5 minutes)
        });
        bytes memory attestationSignatureThird = _signAttestation(attestationThird, attesterKey);

        vm.expectRevert(VisitRegistry.DailyCapExceeded.selector);
        registry.claim(sigThird, signatureThird, attestationThird, attestationSignatureThird);
    }
}