#!/usr/bin/env python
from flask import (Flask, jsonify, render_template,
                   request)
import pymongo

app = Flask(__name__)

client = pymongo.MongoClient()
db = client.zcashdb
AddressTransaction = db['zecaddresstransactions']
Blocks = db['zecblocks']
Transactions = db['zectransactions']
TxOutputs = db['zectxoutputs']


@app.route('/')
def index():
    block = Blocks.find_one(sort=[('height', pymongo.DESCENDING)])
    recent_blocks = [
        block for block in
        Blocks.find(sort=[('height', pymongo.DESCENDING)], limit=10)
    ]
    return render_template('index.html',
                           blockchain=block,
                           recent_blocks=recent_blocks)


@app.route('/block/<hash>')
def block(hash):
    if len(hash) == 64:
        block = Blocks.find_one({'hash': hash})
    else:
        block = Blocks.find_one({'height': int(hash)})
    prevblock = Blocks.find_one({'height': int(block['height']) - 1})
    nextblock = Blocks.find_one({'height': int(block['height']) + 1})
    transactions = Transactions.find({'blockhash': block['hash']}) \
        .sort('blockindex', pymongo.ASCENDING)
    txs = []
    for tx in transactions:
        txs.append(tx)
        tx['out'] = TxOutputs.find({'txid': tx['txid']},
                                   sort=[('pos', pymongo.ASCENDING)])
    return render_template('block.html',
                           block=block,
                           transactions=txs,
                           prevblock=prevblock,
                           nextblock=nextblock)


@app.route('/api/v1/transaction/<txid>', methods=['GET'])
def transaction(txid):
    transaction = Transactions.find_one({'txid': txid})
    transaction['out'] = TxOutputs.find({'txid': transaction['txid']},
                                        sort=[('pos', pymongo.ASCENDING)])
    prevtransaction = Transactions.find_one({
        'blockhash': transaction['blockhash'],
        'blockindex': {"$lt": int(transaction['blockindex'])}},
        sort=[('blockheight', pymongo.DESCENDING)])
    nexttransaction = Transactions.find_one({
        'blockhash': transaction['blockhash'],
        'blockindex': {"$gt": int(transaction['blockindex'])}},
        sort=[('blockheight', pymongo.ASCENDING)])
    return render_template('transaction.html',
                           transaction=transaction,
                           prevtransaction=prevtransaction,
                           nexttransaction=nexttransaction)


@app.route('/api/v1/address/<address>', methods=['GET'])
def address(address):
    outputs = []
    confirmed = 0;
    for output in TxOutputs.find({'address': address, 'spent': False}):
        confirmed += int(output['satoshis'])
        outputs.append(output)
    balance = {
        'confirmed': { 'amount': confirmed },
        'unconfirmed': { 'amount': 0 }
    }
    transactions = AddressTransaction.find({'address': address}) \
        .sort('txtime', pymongo.DESCENDING).limit(10)
    txs = []
    for tx in transactions:
        txs.append(tx)
        tx['out'] = TxOutputs.find({'txid': tx['txid']},
                                   sort=[('pos', pymongo.ASCENDING)])
    return render_template('address.html',
                           address=address,
                           balance=balance,
                           transactions=txs,
                           outputs=outputs)


@app.route('/api/v1/blockchaininfo', methods=['GET'])
def get_blockchain_info():
    block = Blocks.find_one(sort=[('height', pymongo.DESCENDING)])
    block.pop('_id')
    return jsonify(block)


@app.route('/api/v1/block/<hash>', methods=['GET'])
def get_block_info(hash):
    hashes = hash.split(",")
    response = {}
    for hash in hashes:
        if len(hash) == 64:
            block = Blocks.find_one({'hash': hash})
        else:
            block = Blocks.find_one({'height': int(hash)})
        if block:
            block.pop('_id')
            transactions = Transactions.find({'blockhash': block['hash']}) \
                .sort('blockindex', pymongo.ASCENDING)
            block['tx'] = [tx['txid'] for tx in transactions]
            response[hash] = block
    return jsonify(response)


@app.route('/api/v1/block', methods=['GET'])
def get_block_list():
    limit = request.args.get('limit', 10)
    blocks = Blocks.find().sort('height', pymongo.DESCENDING).limit(limit)
    response = [block['hash'] for block in blocks]
    return jsonify(response)


@app.route('/api/v1/tx/<txid>', methods=['GET'])
def get_transaction(txid):
    txids = txid.split(",")
    response = {}
    for txid in txids:
        tx = Transactions.find_one({'txid': txid})
        if tx:
            tx.pop('_id')
            outputs = TxOutputs.find({'txid': txid}) \
                .sort('pos', pymongo.ASCENDING)
            tx['out'] = [output for output in outputs]
            for output in tx['out']:
                output.pop('_id')
            response[txid] = tx
    return jsonify(response)


@app.route('/api/v1/address/<address>/balance', methods=['GET'])
def get_address_balance(address):
    addresses = address.split(",")
    response = {}
    for address in addresses:
        unspentOutputs = TxOutputs.find({'address': address, 'spent': False})
        response[address] = {
            'confirmed': {
                'amount': sum([int(unspent['satoshis'])
                               for unspent in unspentOutputs])
            },
            'unconfirmed': {
                'amount': 0
            }
        }
    return jsonify(response)


@app.route('/api/v1/address/<address>/transactions', methods=['GET'])
def get_address_transactions(address):
    addresses = address.split(",")
    response = {}
    for address in addresses:
        transactions = AddressTransaction.find({'address': address}) \
            .sort('txtime', pymongo.DESCENDING)
        response[address] = [tx['txid'] for tx in transactions]
    return jsonify(response)


if __name__ == '__main__':
    app.run(debug=True)
