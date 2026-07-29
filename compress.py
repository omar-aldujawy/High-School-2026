import pandas as pd
print('جاري الضغط...')
df = pd.read_csv('all_students_results.csv')
df.to_csv('all_students_results.csv.gz', index=False, compression='gzip')
print('تم الضغط بنجاح!')
