from sklearn.model_selection import train_test_split
import util



class Devider(object):
    def __init__(self,
                 num_inst,
                 file_path):
        self.num_inst= num_inst
        self.file_path = file_path
        self.owner = file_path.split('_')[0]
        self.repo = file_path.split('_')[1]

    def _gen_class(self, num_inst):
        class_list = []
        for i in range(num_inst):
            if i % 2 == 0:
                class_list.append(1)
            else :
                class_list.append(0)
        return class_list

    def devide(self):
        class_list = self._gen_class(self.num_inst)
        total_list = list(range(self.num_inst))
        # print(len(class_list))
        # print(len(total_list))

        train_idx, val_idx, train_class, val_class = train_test_split(total_list,class_list,test_size = 0.2,shuffle=True,stratify=class_list)
        test_idx, val_idx, _ , _ = train_test_split(val_idx,val_class,test_size = 0.5,shuffle=True,stratify=val_class)
        return train_idx, val_idx, test_idx

    def write(self,train_idx,test_idx,val_idx):
        train_path = util.devided_file_template.format(pro_name=self.repo, type='train')
        val_path = util.devided_file_template.format(pro_name=self.repo, type='val')
        test_path = util.devided_file_template.format(pro_name=self.repo, type='test')

        f_train = open(train_path, 'w', newline='', encoding='UTF-8')
        f_test = open(test_path, 'w', newline='', encoding='UTF-8')
        f_val = open(val_path, 'w', newline='', encoding='UTF-8')

        with open(self.file_path, 'r',encoding='UTF-8') as f:
            lines = f.readlines()
            for idx, line in enumerate(lines):
                if idx in train_idx:
                    f_train.write(line)
                elif idx in val_idx:
                    f_val.write(line)
                else:
                    f_test.write(line)

        f_train.close()
        f_test.close()
        f_val.close()


if __name__ == '__main__':

    devider= Devider(num_inst=196, file_path='./result/yomorun_yomo_GHPR.txt')
    train_idx, val_idx, test_idx= devider.devide()
    devider.write(train_idx,test_idx,val_idx)