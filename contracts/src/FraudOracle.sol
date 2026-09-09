// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {MerkleProof} from "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";

contract FraudOracle {
    address public immutable OPERATOR;

    bytes32 public currentRoot;
    uint64 public currentEpoch;

    event EpochCommitted(uint64 indexed epoch, bytes32 root);

    error NotOperator();
    error EpochNotIncreasing();
    error ZeroRoot();

    constructor(address operator) {
        OPERATOR = operator;
    }

    function commitEpoch(bytes32 root, uint64 epoch) external {
        if (msg.sender != OPERATOR) revert NotOperator();
        if (root == bytes32(0)) revert ZeroRoot();
        if (epoch <= currentEpoch && currentRoot != bytes32(0)) revert EpochNotIncreasing();

        currentRoot = root;
        currentEpoch = epoch;
        emit EpochCommitted(epoch, root);
    }

    function verifyScore(address wallet, uint16 score, bytes32[] calldata proof) external view returns (bool) {
        bytes32 leaf = keccak256(abi.encode(wallet, score));
        leaf = keccak256(abi.encode(leaf));
        return MerkleProof.verify(proof, currentRoot, leaf);
    }
}