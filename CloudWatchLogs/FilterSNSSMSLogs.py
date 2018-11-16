import json

if __name__ == "__main__":
    with open('data.json') as f:
        data = json.load(f)
    i=0
    count =0
    list =[]
    for (i, item) in enumerate(data['events']):
        print(i)
        try:
            if '2018-11-13' in item['message']:
                count +=1
                print(item['message'])
                list.append(item)
        except Exception as e:
            print(e)
    with open('dataOut.json', 'w') as outfile:
        json.dump(list, outfile)

