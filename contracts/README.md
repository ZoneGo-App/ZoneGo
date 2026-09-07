## Foundry

**Foundry is a blazing fast, portable and modular toolkit for Ethereum application development written in Rust.**

Foundry consists of:

- **Forge**: Ethereum testing framework (like Truffle, Hardhat and DappTools).
- **Cast**: Swiss army knife for interacting with EVM smart contracts, sending transactions and getting chain data.
- **Anvil**: Local Ethereum node, akin to Ganache, Hardhat Network.
- **Chisel**: Fast, utilitarian, and verbose solidity REPL.

## Documentation

https://book.getfoundry.sh/

## Usage

### Build

```shell
$ forge build
```

### Test

```shell
$ forge test
```

### Format

```shell
$ forge fmt
```

### Gas Snapshots

```shell
$ forge snapshot
```

### Anvil

```shell
$ anvil
```

### Deploy

```shell
$ forge script script/Counter.s.sol:CounterScript --rpc-url <your_rpc_url> --private-key <your_private_key>
```

### Cast

```shell
$ cast <subcommand>
```

### Help

```shell
$ forge --help
$ anvil --help
$ cast --help
```

## Deployed contracts (Base Sepolia)

- CampaignVault: 0x7447823C46C6E8E7039Ae239cf6F709cBC3CA467

## Deployed contracts (Base Sepolia) — updated

- CampaignVault: 0x01422196A7768839f24E465115Ff97E170186Bf1
- VisitRegistry: 0x1d86E71956c6486c53fD965926c57121E7b1dda0

(Previous CampaignVault deploy at 0x7447823C46C6E8E7039Ae239cf6F709cBC3CA467 is now obsolete.)

## Deployed contracts (Base Sepolia) — current

- CampaignVault: 0xf4ADec71da03c6595CF4624f7d4573C9EDb753B0
- VisitRegistry: 0xD33f2e26f11Fe011835D791EbA1BFE123479998A
- FraudOracle: 0x5157504d3a9683Ca953EF5db1255dE619E110A9B (skeleton only, day 5 pending)

(Previous deploys are now obsolete.)
