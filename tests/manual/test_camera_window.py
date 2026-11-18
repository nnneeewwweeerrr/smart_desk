import cv2

print("正在打开摄像头……")

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("摄像头打开失败")
    exit()

print("摄像头打开成功，准备显示窗口")

while True:
    ret, frame = cap.read()

    if not ret:
        print("读取画面失败")
        break

    cv2.imshow("Camera Test", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

print("测试结束")