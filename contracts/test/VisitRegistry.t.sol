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
    address merchant;
    address visitor = address(0x2);
    uint256 campaignId;

    function setUp() public {
        merchant = vm.addr(merchantKey);
        usdc = new MockUSDC();
        vault = new CampaignVault(address(usdc));
        registry = new VisitRegistry(address(vault));
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

    function test_ReusedNonceReverts() public {
        VisitRegistry.VisitSig memory sig = VisitRegistry.VisitSig({
            campaignId: campaignId,
            nonce: 1,
            expiry: uint64(block.timestamp + 1 hours),
            geohash: bytes32(0),
            visitor: visitor
        });
        bytes memory signature = _sign(sig, merchantKey);
        registry.claim(sig, signature, keccak256("human-1"));

        vm.expectRevert(VisitRegistry.NonceAlreadyUsed.selector);
        registry.claim(sig, signature, keccak256("human-1"));
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

            uint256 balanceBefore = usdc.balanceOf(visitor);
            registry.claim(sig, signature, nullifier);
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

        vm.expectRevert(VisitRegistry.SignatureExpired.selector);
        registry.claim(sig, signature, keccak256("human-1"));
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

        vm.expectRevert(VisitRegistry.BadSig.selector);
        registry.claim(sig, badSignature, keccak256("human-1"));
    }
}