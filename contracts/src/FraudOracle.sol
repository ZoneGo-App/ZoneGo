// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract FraudOracle {
    event EpochCommitted(uint64 indexed epoch, bytes32 root);

    // TODO(day 5)
    function commitEpoch(bytes32 root, uint64 epoch) external {
        revert("not implemented");
    }

    function verifyScore(address wallet, uint16 score, bytes32[] calldata proof) external view returns (bool) {
        revert("not implemented");
    }
}