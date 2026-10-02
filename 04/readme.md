# Commit連結
1. 母專案 -- https://github.com/qaqrain-ex/git_ex/commits/main/  
    * 分支 -- https://github.com/qaqrain-ex/git_ex/commits/testversion  
2. 子專案 -- https://github.com/QAQRain/git_ex/commits/main/  

# 步驟說明

新增 新組織(qaqrain-ex) 及 專案(git_ex)  
ssh至本機(後須說明省略)  
git check -b testversion  
>新增”testversion”分支  
git branch   
>切換分支  

新增testversion.md  
git push origin testversion  
>上傳到testversion分支  
git checkout main  
>檔案切換至main分支，tesetversion.md消失  
git merge testversion  
>合併testversion至main，testversion.md出現  
git push origin main  
>上傳main分支  

在網站Fork給原組織  
本機新增qaqrainfork.md檔案並上傳  
發送合併原組織專案請求  

圖文筆記:  
[點此](https://docs.google.com/document/d/1rNGNbHGCApQ86_E0SypaQNthMb6mGe4oKR8Gd8wm0Bg/edit?usp=sharing)